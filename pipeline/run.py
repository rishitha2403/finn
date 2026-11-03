import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import fundamentals, llm, screener, taxonomy
from pipeline import alerts, enrich, notify, sources
from pipeline.sources import IST

DATA = ROOT / "web" / "public" / "data"
KEEP_DAYS = 30


def log(msg):
    print(f"[{datetime.now(IST):%H:%M:%S}] {msg}", flush=True)


def load(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(path)


class ScreenerCache:
    def __init__(self):
        self.d = {}

    def quarters(self, sym):
        if sym not in self.d:
            try:
                page = screener.fetch(sym)
                self.d[sym] = fundamentals.quarterly(page)
            except Exception as e:
                log(f"screener {sym}: {e}")
                self.d[sym] = None
        return self.d[sym]


def label_items(items):
    for it in items:
        cat = taxonomy.classify(it)
        s, why = taxonomy.score(it, cat)
        it["category"] = cat
        it["score"] = s
        it["why"] = why
        it["tier"] = taxonomy.tier(s)


def enrich_items(items, names, max_summaries):
    sc = ScreenerCache()
    jobs = []
    budget = max_summaries
    for it in sorted(items, key=lambda x: -x["score"]):
        if it.get("enriched"):
            continue
        cat = it["category"]
        if cat == "results" and taxonomy.is_results_filing(it):
            jobs.append(("results", it))
        elif cat == "management_change" and it["score"] >= 60:
            jobs.append(("people", it))
        elif it["score"] >= 40 and cat not in ("earnings_call", "investor_meetings", "agm_egm", "postal_ballot", "results") and budget > 0:
            jobs.append(("line", it))
            budget -= 1

    def work(job):
        kind, it = job
        company = names.get(it["symbol"], it["symbol"])
        try:
            if kind == "results":
                r = enrich.results(it, sc.quarters(it["symbol"]))
                if r:
                    it["results"] = r
            elif kind == "people":
                p = enrich.people(it, company)
                if p:
                    it["people"] = p.get("people") or []
                    if p.get("line"):
                        it["summary"] = p["line"]
            else:
                o = enrich.oneliner(it, company)
                if o:
                    it["summary"] = o.get("line")
                    if o.get("material") is True and it["score"] < 70:
                        it["score"] = min(100, it["score"] + 10)
                        it["model_flag"] = "raised"
                    elif o.get("material") is False and it["score"] >= 40:
                        it["score"] = max(0, it["score"] - 8)
                        it["model_flag"] = "lowered"
                    it["tier"] = taxonomy.tier(it["score"])
            it["enriched"] = True
        except Exception as e:
            it["enrich_error"] = str(e)[:200]
            log(f"enrich {kind} {it['symbol']}: {e}")

    log(f"enriching {len(jobs)} filings")
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(work, jobs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="how many days of filings to fetch")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--max-summaries", type=int, default=int(os.getenv("FINN_MAX_SUMMARIES", "40")))
    a = ap.parse_args()

    t0 = time.time()
    cfg = load(ROOT / "pipeline" / "portfolio.json", {})
    pf = cfg["portfolio"]
    names = {p["symbol"]: p["name"] for p in pf}
    syms = [p["symbol"] for p in pf]
    status = {}

    log("prices")
    try:
        eod = sources.prices(syms)
        status["prices"] = f"ok ({len(eod)}/{len(syms)})"
        save(DATA / "eod.json", eod)
    except Exception as e:
        log(f"prices failed: {e}")
        status["prices"] = f"failed: {e}"[:120]
        eod = load(DATA / "eod.json", {})

    old = load(DATA / "filings.json", [])
    known = {f["id"]: f for f in old}
    days = a.days or (4 if old else KEEP_DAYS)
    log(f"announcements, last {days} days")
    fresh, ann_status = sources.announcements(pf, days, log)
    status["announcements"] = ann_status
    new = [f for f in fresh if f["id"] not in known and f.get("ts")]
    log(f"{len(fresh)} fetched, {len(new)} new")
    label_items(new)

    if not a.no_llm and llm.available():
        enrich_items(new, names, a.max_summaries)
    elif not llm.available():
        log("GEMINI_API_KEY not set: skipping summaries and results extraction")

    merged = list(known.values()) + new
    cutoff = (datetime.now(IST) - timedelta(days=KEEP_DAYS)).isoformat()
    merged = [f for f in merged if (f.get("ts") or "") >= cutoff]
    merged.sort(key=lambda f: f["ts"], reverse=True)
    save(DATA / "filings.json", merged)

    moves = alerts.scan(eod, last_n=1) if eod else []
    pushed = 0
    if notify.enabled() and not a.no_push:
        fresh_act = [f for f in new if f["tier"] == "act"]
        latest_day = max((rows[-1][0] for rows in eod.values() if rows), default=None)
        last_push_day = load(DATA / "meta.json", {}).get("last_move_push")
        todays_moves = [m for m in moves if m["date"] == latest_day and latest_day != last_push_day]
        text = notify.compose(fresh_act, todays_moves, os.getenv("FINN_APP_URL"))
        if text:
            try:
                notify.send(text)
                pushed = len(fresh_act) + len(todays_moves)
                status["telegram"] = f"sent {pushed}"
            except Exception as e:
                status["telegram"] = f"failed: {e}"[:120]
        last_push = latest_day
    else:
        last_push = load(DATA / "meta.json", {}).get("last_move_push")

    meta = {
        "generated_at": datetime.now(IST).isoformat(),
        "took_s": round(time.time() - t0, 1),
        "portfolio": pf,
        "research_demo": cfg.get("research_demo", []),
        "labels": taxonomy.LABELS,
        "default_watch": taxonomy.DEFAULT_WATCH,
        "default_rules": alerts.DEFAULT_RULES,
        "counts": {
            "filings": len(merged),
            "new": len(new),
            "act": sum(1 for f in merged if f["tier"] == "act"),
        },
        "status": status,
        "usage": llm.ledger.summary(),
        "last_move_push": last_push,
    }
    save(DATA / "meta.json", meta)
    log(f"done in {meta['took_s']}s; llm {meta['usage']}")


if __name__ == "__main__":
    main()

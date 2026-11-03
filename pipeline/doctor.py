import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import fundamentals, llm, screener
from pipeline import sources
from pipeline.sources import IST

OK = "OK  "
BAD = "FAIL"


def check(name, fn):
    t = time.time()
    try:
        msg = fn()
        print(f"  {OK}  {name}: {msg}  ({time.time() - t:.1f}s)")
        return True
    except Exception as e:
        print(f"  {BAD}  {name}: {e}")
        return False


def yahoo():
    d = sources.prices(["TCS", "RELIANCE"], days=40)
    return f"{sum(len(v) for v in d.values())} rows, last {d['TCS'][-1]}"


def bse():
    c = sources._bse_client()
    code = sources.bse_code(c, "TCS") or "532540"
    now = datetime.now(IST)
    items = sources.bse_announcements(c, "TCS", code, now - timedelta(days=20), now)
    c.exit()
    return f"code {code}, {len(items)} filings in 20 days; latest: {items[0]['title'][:60] if items else '-'}"


def nse():
    c = sources._nse_client()
    now = datetime.now(IST)
    items = sources.nse_announcements(c, "TCS", now - timedelta(days=20), now)
    c.exit()
    return f"{len(items)} filings in 20 days"


def scr():
    p = screener.fetch("TCS")
    f = fundamentals.build(p)
    cc = len(p["documents"]["concalls"])
    tr = sum(1 for c in p["documents"]["concalls"] if c.get("transcript"))
    return f"{p['name']}; {len(f['_qs'])} quarters, {len(f['_ys'])} years; {cc} concalls ({tr} with transcripts); latest {f['snapshot']['latest_quarter']}"


def gem():
    if not llm.available():
        raise RuntimeError("GEMINI_API_KEY not set")
    out = llm.ask_json("fast", 'Return {"ok": true} as JSON.')
    s = llm.ask_json("smart", 'Return {"ok": true} as JSON.')
    return f"fast {out}, smart {s}; models {llm.ledger.summary()['by_tier']}"


if __name__ == "__main__":
    os.environ.setdefault("FINN_CACHE_DIR", str(ROOT / ".cache" / "doctor"))
    print("Checking every data source FINN depends on:\n")
    r = [
        check("Yahoo Finance prices", yahoo),
        check("BSE announcements", bse),
        check("NSE announcements (fallback)", nse),
        check("screener.in fundamentals", scr),
        check("Gemini API", gem),
    ]
    print(f"\n{sum(r)}/{len(r)} sources working")

import re
from concurrent.futures import ThreadPoolExecutor

from core import llm, net
from core.fundamentals import fy_label, fy_of, parse_period

EXTRACT_PROMPT = """You are reading the transcript of {company}'s earnings call held in {date}.
Use only this transcript. Do not use anything you know about the company from elsewhere.

Return JSON with exactly these keys:
{{
  "call_quarter": "the quarter being discussed, like Q2 FY27",
  "guidance": [
    {{
      "metric": one of "revenue_growth", "ebitda_margin", "pat_growth", "volume_growth", "capex", "debt", "order_book", "other",
      "statement": "what management committed to, in plain words, max 20 words",
      "quote": "the exact words from the transcript, max 25 words",
      "low": number or null,
      "high": number or null,
      "unit": "%" or "cr" or "other",
      "period": "the period it applies to, written like FY27, Q3 FY27, H2 FY27, or 'medium term'",
      "speaker": "role of the person, like CEO or CFO"
    }}
  ],
  "business": {{
    "what": "one sentence on what the company sells and to whom, from management's own description",
    "segments": [{{"name": "...", "share_pct": number or null, "comment": "max 12 words"}}]
  }},
  "tone": "one sentence on management's tone, with one concrete reason",
  "analyst_pressure": ["topics analysts pushed back on, max 6 words each, at most 4"]
}}

Rules:
- Guidance means an explicit forward number or a clearly stated directional commitment about a future period. Skip vague hopes like "we remain optimistic".
- Growth ranges like "high single digit" become low 7, high 9; "mid teens" becomes 14 to 16; "double digit" becomes low 10, high null.
- Margin guidance uses unit "%" and the margin level, not the change.
- Indian fiscal years run April to March: FY27 is April 2026 to March 2027.
- If there is no guidance, return an empty list. Never invent numbers.
"""

SYNTH_PROMPT = """You are an equity analyst writing for a portfolio manager who has 60 seconds.
Company: {company} ({symbol}). Everything you may use is below: numbers computed from reported financials,
signals derived from them, and what management said on the last few earnings calls.
Do not use any outside knowledge about this company, its industry, or news. If something is not in the material, do not say it.

NUMBERS
{numbers}

SIGNALS FROM THE FINANCIALS
{signals}

GUIDANCE TRACK RECORD (verdicts computed by code where a number could be checked)
{track}

WHAT MANAGEMENT SAID (per call)
{calls}

Return JSON with exactly these keys:
{{
  "read": ["three sentences a PM would underline; each must contain a number from the material"],
  "credibility": {{"score": "high" or "mixed" or "low", "why": "one sentence grounded in the track record"}},
  "qualitative": [{{"id": "guidance id from the track record that has no computed verdict", "verdict": "delivered" or "on track" or "slipping" or "missed" or "too early", "why": "max 20 words citing a number"}}],
  "narrative_vs_numbers": [{{"claim": "what management says, max 15 words", "numbers": "what the financials show, max 18 words", "verdict": "agrees" or "diverges" or "unclear"}}],
  "bull": ["three points, max 22 words each, each tied to a number or a quote"],
  "bear": ["three points, max 22 words each, each tied to a number or a quote"],
  "watch_next": ["two things to check on the next call, max 14 words each"]
}}
Give at most 4 narrative_vs_numbers items. Prefer specific over general. No adjectives like robust, strong, impressive.
"""


def _call_key(c):
    p = parse_period(c.get("date", ""))
    return p or (0, 0)


def recent_transcripts(documents, n=4):
    calls = [c for c in documents.get("concalls", []) if c.get("transcript")]
    calls.sort(key=_call_key, reverse=True)
    return calls[:n]


def extract_one(company, call):
    pdf = net.get_pdf(call["transcript"])
    prompt = EXTRACT_PROMPT.format(company=company, date=call.get("date") or "an unknown month")
    out = llm.ask_json("fast", prompt, pdf=pdf, max_out=3000)
    out["date"] = call.get("date")
    out["url"] = call["transcript"]
    return out


def extract(company, documents, n=4):
    calls = recent_transcripts(documents, n)
    results = []
    errors = []

    def job(c):
        try:
            return extract_one(company, c), None
        except Exception as e:
            return None, f"{c.get('date')}: {e}"

    with ThreadPoolExecutor(max_workers=4) as ex:
        for res, err in ex.map(job, calls):
            if res:
                results.append(res)
            if err:
                errors.append(err)
    results.sort(key=_call_key, reverse=True)
    return {"calls": results, "errors": errors, "available": len(calls)}


def _period(p):
    p = (p or "").upper().replace(" ", "")
    m = re.match(r"^Q([1-4])FY(\d{2,4})$", p)
    if m:
        fy = int(m.group(2)) % 100 + 2000
        return ("Q", fy, int(m.group(1)))
    m = re.match(r"^H([12])FY(\d{2,4})$", p)
    if m:
        fy = int(m.group(2)) % 100 + 2000
        return ("H", fy, int(m.group(1)))
    m = re.match(r"^FY(\d{2,4})(E)?$", p)
    if m:
        fy = int(m.group(1)) % 100 + 2000
        return ("FY", fy, None)
    return None


def _q_of(q):
    return ((q["month"] - 4) % 12) // 3 + 1


def _sum(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) if len(vals) == len(rows) and rows else None


def actual_for(metric, period, qs, ys):
    per = _period(period)
    if not per or metric not in ("revenue_growth", "ebitda_margin", "pat_growth"):
        return None
    kind, fy, n = per
    if kind == "FY":
        yr = next((y for y in ys if y["fy"] == fy), None)
        if yr and yr["revenue"] is not None:
            if metric == "revenue_growth":
                return {"value": yr["revenue_growth"], "basis": f"{fy_label(fy)} full year", "final": True}
            if metric == "pat_growth":
                return {"value": yr["pat_growth"], "basis": f"{fy_label(fy)} full year", "final": True}
            return {"value": yr["opm"], "basis": f"{fy_label(fy)} full year", "final": True}
        cur = [q for q in qs if q["fy"] == fy]
        if not cur:
            return None
        prev = [q for q in qs if q["fy"] == fy - 1 and _q_of(q) <= len(cur)]
        label = f"{fy_label(fy)} first {len(cur)} quarter{'s' if len(cur) > 1 else ''}"
        if metric == "ebitda_margin":
            r = _sum(cur, "revenue")
            o = _sum(cur, "op")
            if r and o is not None:
                return {"value": round(o / r * 100, 1), "basis": label, "final": False}
            return None
        k = "revenue" if metric == "revenue_growth" else "pat"
        a = _sum(cur, k)
        b = _sum(prev, k)
        if a is None or not b or len(prev) != len(cur) or b <= 0:
            return None
        return {"value": round((a / b - 1) * 100, 1), "basis": label + " vs last year", "final": False}
    if kind == "Q":
        q = next((x for x in qs if x["fy"] == fy and _q_of(x) == n), None)
        if not q:
            return None
        if metric == "revenue_growth":
            v = q.get("revenue_yoy")
        elif metric == "pat_growth":
            v = q.get("pat_yoy")
        else:
            v = q.get("opm")
        if v is None:
            return None
        return {"value": v, "basis": q["label"], "final": True}
    return None


def verdict(item, act):
    lo = item.get("low")
    hi = item.get("high")
    if act is None or (lo is None and hi is None):
        return None
    v = act["value"]
    if v is None:
        return None
    tol = 0.2
    if lo is not None and v < lo - tol:
        return "behind" if not act["final"] else "missed"
    if hi is not None and v > hi + tol:
        return "ahead" if not act["final"] else "beat"
    return "on track" if not act["final"] else "met"


def track_record(extracted, qs, ys):
    items = []
    i = 0
    for call in extracted.get("calls", []):
        for g in call.get("guidance", []) or []:
            i += 1
            act = actual_for(g.get("metric"), g.get("period"), qs, ys)
            items.append({
                "id": f"g{i}",
                "said_on": call.get("date"),
                "call_quarter": call.get("call_quarter"),
                "metric": g.get("metric"),
                "statement": g.get("statement"),
                "quote": g.get("quote"),
                "low": g.get("low"),
                "high": g.get("high"),
                "unit": g.get("unit"),
                "period": g.get("period"),
                "speaker": g.get("speaker"),
                "actual": act,
                "verdict": verdict(g, act),
                "source": call.get("url"),
            })
    return items


def compact_numbers(f):
    s = f["snapshot"]
    t = f["trajectory"]
    b = f["balance"]
    c = f["cash"]
    lines = [
        f"Market cap ₹{s.get('market_cap')} cr, P/E {s.get('pe')}, ROCE {s.get('roce')}%, ROE {s.get('roe')}%",
        f"TTM revenue ₹{s.get('ttm_revenue')} cr, TTM operating margin {s.get('ttm_opm')}%, TTM PAT ₹{s.get('ttm_pat')} cr",
        f"3-yr revenue CAGR {t.get('rev_cagr_3y')}%, 3-yr PAT CAGR {t.get('pat_cagr_3y')}%, margin change 3y {t.get('opm_change_3y')} pts",
        f"Debt/equity {b.get('de')}, cash conversion cycle {b.get('ccc')} days",
        f"5-yr operating cash / PAT {c.get('conversion')}, 5-yr free cash flow est ₹{c.get('fcf_sum')} cr",
        "Quarters (label: revenue cr, YoY %, op margin %, PAT cr, PAT YoY %):",
    ]
    for q in f["quarters"]:
        lines.append(f"  {q['label']}: {q['revenue']}, {q['revenue_yoy']}, {q['opm']}, {q['pat']}, {q['pat_yoy']}")
    lines.append("Years (label: revenue cr, growth %, op margin %, PAT cr):")
    for y in t.get("years", []):
        lines.append(f"  {y['label']}: {y['revenue']}, {y['revenue_growth']}, {y['opm']}, {y['pat']}")
    return "\n".join(lines)


def synthesize(f, extracted, track):
    signals = "\n".join(f"- [{s['kind']}] {s['text']}" for s in f["signals"]) or "- none"
    tr = []
    for t in track:
        a = t["actual"]
        act = f"actual {a['value']} ({a['basis']})" if a else "no computed actual"
        tr.append(f"- {t['id']} said {t['said_on']}: {t['statement']} [period {t['period']}] -> {t['verdict'] or 'not computed'}; {act}")
    calls = []
    for c in extracted.get("calls", []):
        calls.append(f"- {c.get('date')} ({c.get('call_quarter')}): tone: {c.get('tone')}; analysts pressed on: {', '.join(c.get('analyst_pressure') or [])}")
    prompt = SYNTH_PROMPT.format(
        company=f["name"],
        symbol=f["symbol"],
        numbers=compact_numbers(f),
        signals=signals,
        track="\n".join(tr) or "- no explicit guidance found",
        calls="\n".join(calls) or "- no transcripts available",
    )
    return llm.ask_json("smart", prompt, max_out=3000, temperature=0.2)

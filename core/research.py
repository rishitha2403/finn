import time

from core import fundamentals, guidance, llm, screener


def numbers(symbol):
    page = screener.fetch(symbol)
    f = fundamentals.build(page)
    return page, f


def stage_numbers(symbol):
    t = time.time()
    page, f = numbers(symbol)
    out = fundamentals.public(f)
    out["about"] = page.get("about")
    out["took_s"] = round(time.time() - t, 1)
    out["llm_ready"] = llm.available()
    return out


def stage_guidance(symbol):
    t = time.time()
    page, f = numbers(symbol)
    ext = guidance.extract(f["name"], f["documents"])
    track = guidance.track_record(ext, f["_qs"], f["_ys"])
    latest = ext["calls"][0] if ext["calls"] else {}
    return {
        "symbol": f["symbol"],
        "calls": [{k: c.get(k) for k in ("date", "call_quarter", "tone", "analyst_pressure", "url")} for c in ext["calls"]],
        "business": latest.get("business"),
        "track": track,
        "errors": ext["errors"],
        "transcripts_found": ext["available"],
        "took_s": round(time.time() - t, 1),
        "_extracted": ext,
    }


def stage_synthesis(symbol, g):
    t = time.time()
    page, f = numbers(symbol)
    ext = g.get("_extracted") or {"calls": g.get("calls", [])}
    syn = guidance.synthesize(f, ext, g.get("track", []))
    syn["took_s"] = round(time.time() - t, 1)
    return syn


def full(symbol):
    llm.ledger.reset()
    n = stage_numbers(symbol)
    out = {"symbol": n["symbol"], "numbers": n, "prepared_at": int(time.time())}
    if not llm.available():
        out["story_error"] = "GEMINI_API_KEY is not set"
        return out
    try:
        g = stage_guidance(symbol)
        s = stage_synthesis(symbol, g)
        g.pop("_extracted", None)
        out["guidance"] = g
        out["synthesis"] = s
    except Exception as e:
        out["story_error"] = str(e)
    out["usage"] = llm.ledger.summary()
    return out

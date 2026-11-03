from core import llm, net
from core.fundamentals import pct

RESULTS_PROMPT = """This PDF is a quarterly financial results filing by an Indian listed company ({symbol}).
Read the results table. Prefer the CONSOLIDATED statement if both consolidated and standalone are present.
Return JSON:
{{
  "basis": "consolidated" or "standalone",
  "is_bank_or_nbfc": true or false,
  "period": "the latest quarter, like Q2 FY27 (Indian FY runs April-March)",
  "unit": "crore" or "lakh" or "million" or "thousand",
  "columns": ["date of latest quarter", "date of previous quarter", "date of same quarter last year"],
  "revenue": [latest, previous quarter, same quarter last year],
  "other_income": [3 numbers],
  "finance_costs": [3 numbers],
  "depreciation": [3 numbers],
  "pbt_before_exceptional": [3 numbers or nulls],
  "exceptional": [3 numbers or nulls, negative if it reduced profit],
  "pbt": [3 numbers],
  "pat": [3 numbers, profit for the period attributable to owners if shown, else total profit],
  "notes": ["at most 2 short facts from the filing a fund manager must know, like an exceptional item or a one-off, max 15 words each"]
}}
"revenue" is revenue from operations (for banks: total interest earned). Copy numbers exactly as printed; use null when a line is missing. Do not compute anything."""

PEOPLE_PROMPT = """This PDF is a disclosure by {company} ({symbol}) about a change in directors or key managerial personnel.
Return JSON:
{{
  "people": [
    {{
      "name": "full name",
      "role": "the role, like Chief Financial Officer",
      "change": "appointed" or "resigned" or "retired" or "ceased" or "re-appointed" or "redesignated",
      "effective": "date if stated, else null",
      "reason": "stated reason, max 12 words, else null",
      "background": "brief profile as disclosed in the filing, max 40 words, else null",
      "previously": ["up to 3 prior employers or roles named in the filing"],
      "education": "qualifications if stated, else null"
    }}
  ],
  "line": "one sentence, max 22 words, saying who is in, who is out, and for which role"
}}
Use only the PDF. SEBI requires a brief profile for appointments; copy its facts, do not add any."""

ONELINER_PROMPT = """This PDF is an exchange filing by {company} ({symbol}) titled: "{title}".
A fund manager will read one line about it on a phone. Return JSON:
{{"line": "max 24 words: what happened, with the single most important number or date in the filing", "material": true or false}}
"material" is true only if this could plausibly move the stock (size, money, legal exposure, guidance, control).
Use only the PDF."""


def _pdf(item):
    for u in (item.get("url"), item.get("url_alt")):
        if not u:
            continue
        try:
            return net.get_pdf(u)
        except Exception:
            continue
    return None


UNITS = {"crore": 1, "cr": 1, "lakh": 0.01, "lakhs": 0.01, "million": 0.1, "mn": 0.1, "thousand": 0.0001}


def _col(arr, i):
    if not arr or i >= len(arr):
        return None
    v = arr[i]
    if isinstance(v, str):
        try:
            v = float(v.replace(",", "").replace("(", "-").replace(")", ""))
        except ValueError:
            return None
    return v


def headline_numbers(raw):
    f = UNITS.get(str(raw.get("unit", "crore")).lower().strip(), 1)
    out = {}
    for i, key in enumerate(("cur", "prev_q", "prev_y")):
        rev = _col(raw.get("revenue"), i)
        oi = _col(raw.get("other_income"), i)
        fc = _col(raw.get("finance_costs"), i)
        dep = _col(raw.get("depreciation"), i)
        pbt_pre = _col(raw.get("pbt_before_exceptional"), i)
        pbt = _col(raw.get("pbt"), i)
        pat = _col(raw.get("pat"), i)
        base = pbt_pre if pbt_pre is not None else pbt
        ebitda = None
        if not raw.get("is_bank_or_nbfc") and None not in (base, fc, dep):
            ebitda = base + fc + dep - (oi or 0)
        conv = lambda v: round(v * f, 1) if v is not None else None
        out[key] = {
            "revenue": conv(rev),
            "ebitda": conv(ebitda),
            "pbt": conv(pbt),
            "pat": conv(pat),
        }
    rows = []
    for k, name in (("revenue", "Revenue"), ("ebitda", "EBITDA"), ("pbt", "PBT"), ("pat", "PAT")):
        c = out["cur"][k]
        rows.append({
            "key": k,
            "name": name,
            "cur": c,
            "qoq": pct(c, out["prev_q"][k]),
            "yoy": pct(c, out["prev_y"][k]),
            "prev_q": out["prev_q"][k],
            "prev_y": out["prev_y"][k],
        })
    margin = None
    if out["cur"]["ebitda"] is not None and out["cur"]["revenue"]:
        margin = round(out["cur"]["ebitda"] / out["cur"]["revenue"] * 100, 1)
    return rows, margin


def crosscheck(rows, screener_qs):
    if not screener_qs:
        return {"status": "unchecked"}
    last = screener_qs[-1]
    rev = next(r for r in rows if r["key"] == "revenue")["cur"]
    pat = next(r for r in rows if r["key"] == "pat")["cur"]
    if rev is None or last.get("revenue") is None:
        return {"status": "unchecked"}
    d = abs(rev / last["revenue"] - 1) if last["revenue"] else 1
    if d <= 0.02:
        return {"status": "match", "against": last["label"]}
    for q in screener_qs[-3:]:
        if q.get("revenue") and abs(rev / q["revenue"] - 1) <= 0.02:
            return {"status": "match", "against": q["label"]}
    return {"status": "differs", "against": last["label"], "screener_revenue": last["revenue"], "screener_pat": last.get("pat"), "filing_pat": pat}


def results(item, screener_qs=None):
    pdf = _pdf(item)
    if pdf is None:
        return None
    prompt = RESULTS_PROMPT.format(symbol=item["symbol"])
    raw = llm.ask_json("fast", prompt, pdf=pdf, max_out=2500)
    rows, margin = headline_numbers(raw)
    check = crosscheck(rows, screener_qs)
    model = "fast"
    if check["status"] == "differs":
        raw2 = llm.ask_json("smart", prompt, pdf=pdf, max_out=2500)
        rows2, margin2 = headline_numbers(raw2)
        check2 = crosscheck(rows2, screener_qs)
        if check2["status"] == "match" or rows2[0]["cur"] is not None:
            raw, rows, margin, check, model = raw2, rows2, margin2, check2, "smart"
    return {
        "period": raw.get("period"),
        "basis": raw.get("basis"),
        "lender": bool(raw.get("is_bank_or_nbfc")),
        "rows": rows,
        "ebitda_margin": margin,
        "notes": (raw.get("notes") or [])[:2],
        "check": check,
        "extracted_by": model,
    }


def people(item, company):
    pdf = _pdf(item)
    if pdf is None:
        return None
    return llm.ask_json("fast", PEOPLE_PROMPT.format(company=company, symbol=item["symbol"]), pdf=pdf, max_out=1500)


def oneliner(item, company):
    pdf = _pdf(item)
    if pdf is None:
        return None
    return llm.ask_json("fast", ONELINER_PROMPT.format(company=company, symbol=item["symbol"], title=item.get("title") or item.get("subject")), pdf=pdf, max_out=300)

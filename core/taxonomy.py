import re

LABELS = {
    "results": "Results",
    "M&A": "M&A",
    "fund_raise": "Fund raise",
    "management_change": "Management change",
    "litigation": "Litigation & regulatory",
    "insider_trading": "Insider trade",
    "earnings_call": "Earnings call",
    "investor_meetings": "Investor meetings",
    "credit_rating": "Credit rating",
    "dividend": "Dividend",
    "bonus_split": "Bonus / split",
    "capex": "Capex",
    "press_release": "Press release",
    "postal_ballot": "Postal ballot",
    "agm_egm": "AGM / EGM",
    "pledging": "Pledging",
    "unclassified": "Routine paperwork",
}

DEFAULT_WATCH = ["results", "M&A", "management_change", "fund_raise", "litigation", "credit_rating", "pledging"]


def _any(t, words):
    return any(w in t for w in words)


NOISE = [
    "trading window", "loss of share", "duplicate share", "duplicate certificate", "reg. 74", "regulation 74",
    "esop", "esos", "esps", "employee stock", "certificate under", "compliance certificate",
    "statement of investor complaints", "investor complaint", "shareholding pattern", "reconciliation of share capital",
    "business responsibility", "brsr", "esg report", "sustainability report", "secretarial compliance",
    "statement of deviation", "change in registrar", "share transfer agent", "closure of register",
    "copy of newspaper", "newspaper publication", "newspaper advertisement", "intimation of record date for interest",
    "large corporate", "disclosure under regulation 23", "related party transactions",
]

RULES = [
    ("earnings_call", ["transcript", "earnings call", "conference call", "concall", "con call", "audio recording", "audio/video recording", "recording of"]),
    ("investor_meetings", ["analyst / investor meet", "analyst/investor meet", "analysts/institutional investor", "investor meet", "analyst meet", "institutional investor", "one-on-one", "roadshow", "investor conference"]),
    ("pledging", ["pledge", "encumbrance"]),
    ("insider_trading", ["insider trading", "sast", "regulation 7(2)", "reg. 7(2)", "regulation 29", "regulation 31", "substantial acquisition"]),
    ("credit_rating", ["credit rating", "rating action", "crisil", "icra", "care ratings", "care edge", "india ratings", "brickwork", "acuite", "fitch", "moody"]),
    ("results", ["financial result", "results for the quarter", "results for quarter", "unaudited result", "audited result", "integrated filing (financial)", "integrated filing- financial", "investor presentation", "earnings presentation", "results presentation"]),
    ("management_change", ["change in director", "key managerial", "kmp", "appointment of", "re-appointment", "reappointment", "resignation", "resigns", "cessation", "retirement", "retire", "chief executive", "chief financial", "managing director", "whole-time director", "whole time director", "senior management"]),
    ("M&A", ["acquisition", "acquire", "amalgamation", "merger", "demerger", "scheme of arrangement", "joint venture", "stake sale", "divest", "slump sale", "investment in subsidiary", "incorporation of", "wholly owned subsidiary", "wos"]),
    ("fund_raise", ["qualified institution", "qip", "rights issue", "preferential issue", "preferential allotment", "buyback", "buy-back", "buy back", "commercial paper", "non-convertible debenture", "ncd", "fund raising", "raising of funds", "raise funds", "warrants"]),
    ("litigation", ["litigation", "penalty", "show cause", "demand order", "tax demand", "gst", "court", "tribunal", "nclt", "nclat", "insolvency", "sebi order", "adjudicat", "dispute", "regulatory action", "search and seizure", "income tax search", "fine imposed"]),
    ("bonus_split", ["bonus", "sub-division", "subdivision", "stock split", "split of"]),
    ("dividend", ["dividend"]),
    ("capex", ["capacity expansion", "new plant", "new facility", "capex", "capital expenditure", "commissioning", "commercial production", "greenfield", "brownfield", "expansion of capacity", "manufacturing facility"]),
    ("postal_ballot", ["postal ballot"]),
    ("agm_egm", ["annual general meeting", "agm", "extra-ordinary general", "extraordinary general", "egm", "e-voting", "scrutinizer"]),
    ("press_release", ["press release", "media release", "order", "contract", "launch", "partnership", "collaboration", "clarification", "agreement", "mou", "award", "bags", "wins", "update"]),
]

TOP_ROLES = ["chief executive", "ceo", "managing director", "md", "chief financial", "cfo", "chairman", "chairperson"]
MID_ROLES = ["whole-time director", "whole time director", "executive director", "chief operating", "coo", "president", "business head", "senior management", "cto", "chief technology"]
LOW_ROLES = ["company secretary", "compliance officer", "independent director", "non-executive", "nominee director"]


def _text(item):
    parts = [item.get("category_raw"), item.get("subcategory_raw"), item.get("title"), item.get("subject")]
    return " ".join(p for p in parts if p).lower()


def classify(item):
    t = _text(item)
    sub = (item.get("subcategory_raw") or "").lower()
    cat = (item.get("category_raw") or "").lower()
    if "auditor" in t and "resign" not in t:
        return "unclassified"
    if _any(t, NOISE) and not _any(t, ["financial result", "acquisition", "resignation", "appointment of chief", "appointment of managing"]):
        if "newspaper" in t and "result" in t:
            return "results"
        return "unclassified"
    if cat.startswith("result") or "financial results" in sub:
        return "results"
    if "insider trading" in cat or "sast" in cat:
        return "pledging" if _any(t, ["pledge", "encumbrance"]) else "insider_trading"
    if "agm" in cat or "egm" in cat:
        return "agm_egm"
    if "board meeting" in cat or "board meeting" in sub:
        if _any(t, ["financial result", "results"]):
            return "results"
        if _any(t, ["dividend"]):
            return "dividend"
        if _any(t, ["fund", "qip", "preferential", "buyback", "buy-back", "rights"]):
            return "fund_raise"
        if _any(t, ["bonus", "split", "sub-division"]):
            return "bonus_split"
    for name, words in RULES:
        for w in words:
            if len(w) <= 4:
                if re.search(rf"\b{re.escape(w)}\b", t):
                    return name
            elif w in t:
                return name
    if "corp. action" in cat:
        return "dividend" if "dividend" in t else "bonus_split" if "bonus" in t or "split" in t else "unclassified"
    return "unclassified"


def _role_rank(t):
    for r in TOP_ROLES:
        if re.search(rf"\b{re.escape(r)}\b", t):
            return 3
    for r in MID_ROLES:
        if re.search(rf"\b{re.escape(r)}\b", t):
            return 2
    for r in LOW_ROLES:
        if r in t:
            return 1
    return 2


def is_results_filing(item):
    t = _text(item)
    if "intimation" in t and "outcome" not in t:
        return False
    if _any(t, ["newspaper", "presentation", "transcript", "call"]):
        return False
    return _any(t, ["financial result", "unaudited", "audited", "integrated filing"]) or (item.get("category_raw") or "").lower().startswith("result")


def score(item, category):
    t = _text(item)
    why = LABELS[category]
    s = 5
    if category == "results":
        if "newspaper" in t:
            s, why = 10, "Results ad in newspapers"
        elif _any(t, ["presentation"]):
            s, why = 55, "Results presentation"
        elif "intimation" in t and "outcome" not in t:
            s, why = 30, "Results date announced"
        elif is_results_filing(item):
            s, why = 95, "Quarterly results"
        else:
            s, why = 60, "Results-related"
    elif category == "management_change":
        rank = _role_rank(t)
        s = {3: 88, 2: 68, 1: 42}[rank]
        why = {3: "Top management change", 2: "Senior management change", 1: "Board / secretarial change"}[rank]
        if "re-appointment" in t or "reappointment" in t or "continuation" in t:
            s -= 25
            why = "Re-appointment"
    elif category == "M&A":
        s, why = 82, "Acquisition / restructuring"
        if _any(t, ["incorporation", "wholly owned subsidiary", "wos"]) and not _any(t, ["acquisition", "acquire", "merger"]):
            s, why = 45, "New subsidiary"
    elif category == "fund_raise":
        s, why = 80, "Equity raise or buyback"
        if _any(t, ["commercial paper", "ncd", "debenture"]) and not _any(t, ["qip", "rights", "preferential", "buyback", "buy-back"]):
            s, why = 38, "Debt raise"
    elif category == "litigation":
        s, why = 62, "Litigation / regulatory"
        if re.search(r"(rs\.?|inr|₹)\s?[\d,\.]+\s*(crore|cr)", t):
            s, why = 74, "Litigation with a stated amount"
    elif category == "insider_trading":
        s, why = 42, "Insider / promoter trade"
        if "promoter" in t:
            s = 52
    elif category == "pledging":
        s, why = 58, "Promoter pledge change"
        if _any(t, ["creation", "invocation", "invoked"]):
            s, why = 74, "Promoter pledged / invoked shares"
        elif "release" in t:
            s, why = 40, "Promoter released pledge"
    elif category == "credit_rating":
        s, why = 45, "Credit rating action"
        if "downgrad" in t or "negative" in t or "watch with negative" in t:
            s, why = 80, "Credit rating downgrade"
        elif "upgrad" in t or "positive" in t:
            s, why = 62, "Credit rating upgrade"
        elif "reaffirm" in t:
            s, why = 28, "Rating reaffirmed"
    elif category == "dividend":
        s, why = 40, "Dividend"
    elif category == "bonus_split":
        s, why = 58, "Bonus or split"
    elif category == "capex":
        s, why = 66, "Capacity / capex"
    elif category == "press_release":
        s, why = 44, "Company update"
        if _any(t, ["order", "contract", "bags", "wins", "award"]):
            s, why = 56, "Order / contract"
        if _any(t, ["business update", "operational update", "quarterly update"]):
            s, why = 54, "Business update"
        if "clarification" in t:
            s, why = 50, "Clarification on news"
    elif category == "earnings_call":
        s, why = 22, "Call scheduled"
        if "transcript" in t:
            s, why = 52, "Call transcript out"
        elif "recording" in t:
            s, why = 18, "Call recording"
    elif category == "investor_meetings":
        s, why = 14, "Investor meeting"
    elif category == "postal_ballot":
        s, why = 24, "Postal ballot"
    elif category == "agm_egm":
        s, why = 22, "AGM / EGM"
        if "egm" in t or "extra" in t:
            s = 40
    if item.get("critical"):
        s += 8
    s = max(0, min(100, s))
    return s, why


def tier(s):
    if s >= 70:
        return "act"
    if s >= 40:
        return "know"
    return "routine"

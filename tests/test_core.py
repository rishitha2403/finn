import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from core import fundamentals, guidance, llm, screener, taxonomy
from pipeline import alerts, enrich
from tests import fake_screener


@pytest.fixture
def page():
    return screener.parse_page(fake_screener.page(), "https://www.screener.in/company/FAKE/consolidated/", "FAKE")


def test_parse_basic(page):
    assert page["name"] == "Fake Industries Ltd"
    assert page["bse_code"] == "512345"
    assert page["ratios"]["Market Cap"] == 45000
    assert page["ratios"]["Stock P/E"] == 42.5
    assert page["quarters"]["rows"]["Sales"][-1] == 1520
    assert "Raw PDF" not in page["quarters"]["rows"]
    assert page["growth"]["Compounded Sales Growth"]["3 Years"] == 13
    cc = page["documents"]["concalls"]
    assert cc[0]["date"] == "Oct 2026"
    assert cc[0]["transcript"].endswith("oct26.pdf")
    assert cc[0]["ppt"] == "https://www.screener.in/ppt"
    assert page["documents"]["annual_reports"][0]["title"].startswith("Financial Year 2026")


def test_clean_symbol():
    assert screener.clean_symbol(" tcs.ns ") == "TCS"
    assert screener.clean_symbol("BAJAJ-AUTO") == "BAJAJ-AUTO"
    assert screener.clean_symbol("M&M") == "M&M"
    with pytest.raises(ValueError):
        screener.clean_symbol("../etc")


def test_period_labels():
    assert fundamentals.quarter_label(2026, 9) == "Q2 FY27"
    assert fundamentals.quarter_label(2026, 3) == "Q4 FY26"
    assert fundamentals.quarter_label(2025, 12) == "Q3 FY26"
    assert fundamentals.quarter_label(2026, 6) == "Q1 FY27"


def test_fundamentals(page):
    f = fundamentals.build(page)
    qs = f["_qs"]
    assert qs[-1]["label"] == "Q2 FY27"
    assert qs[-1]["revenue_yoy"] == round((1520 / 1320 - 1) * 100, 1)
    s = f["snapshot"]
    assert s["ttm_revenue"] == 1360 + 1420 + 1450 + 1520
    assert f["trajectory"]["rev_cagr_3y"] == fundamentals.cagr(5600, 3900, 3)
    b = f["balance"]
    assert b["de"] == round(1300 / 4100, 2)
    ys = f["_ys"]
    last = ys[-1]
    assert last["capex_est"] == (1850 - 1700) + 140 + (100 - 120)
    assert last["fcf_est"] == 700 - last["capex_est"]
    assert f["cash"]["years"] == 5
    kinds = {x["area"] for x in f["signals"]}
    assert "balance" in kinds
    assert any("Receivable days" in x["text"] for x in f["signals"])
    assert f["ownership"]["promoter_change_4q"] == -1.8
    json.dumps(fundamentals.public(f))


def test_lender(page):
    p = screener.parse_page(fake_screener.page(lender=True), "u", "FAKEBANK")
    f = fundamentals.build(p)
    assert f["lender"] is True
    assert f["balance"]["de"] is None
    assert f["_qs"][-1]["op"] is not None


def test_guidance_verdicts(page):
    f = fundamentals.build(page)
    qs, ys = f["_qs"], f["_ys"]
    a = guidance.actual_for("revenue_growth", "FY26", qs, ys)
    assert a["final"] and a["value"] == round((5600 / 4900 - 1) * 100, 1)
    assert guidance.verdict({"low": 12, "high": 15}, a) in ("met", "beat")
    ytd = guidance.actual_for("revenue_growth", "FY27", qs, ys)
    assert ytd["final"] is False
    assert ytd["value"] == round(((1450 + 1520) / (1260 + 1320) - 1) * 100, 1)
    assert guidance.verdict({"low": 20, "high": 22}, ytd) == "behind"
    m = guidance.actual_for("ebitda_margin", "Q2 FY27", qs, ys)
    assert m["basis"] == "Q2 FY27"
    assert guidance.actual_for("capex", "FY27", qs, ys) is None
    assert guidance.actual_for("revenue_growth", "medium term", qs, ys) is None


def test_track_record(page):
    f = fundamentals.build(page)
    ext = {"calls": [{"date": "Oct 2026", "call_quarter": "Q2 FY27", "url": "u", "guidance": [
        {"metric": "revenue_growth", "statement": "Mid-teens growth in FY27", "low": 14, "high": 16, "period": "FY27"},
        {"metric": "capex", "statement": "Capex of 500 cr", "low": 500, "high": 500, "unit": "cr", "period": "FY27"},
    ]}]}
    tr = guidance.track_record(ext, f["_qs"], f["_ys"])
    assert tr[0]["verdict"] in ("on track", "behind", "ahead")
    assert tr[1]["verdict"] is None
    assert "Q2 FY27" in guidance.compact_numbers(fundamentals.build(page))


def test_recent_transcripts(page):
    calls = guidance.recent_transcripts(page["documents"], 4)
    assert [c["date"] for c in calls] == ["Oct 2026", "Jul 2026", "May 2026", "Jan 2026"]


CASES = [
    ({"category_raw": "Result", "subcategory_raw": "Financial Results", "title": "Unaudited Financial Results for the quarter ended September 30, 2026"}, "results", "act"),
    ({"category_raw": "Company Update", "subcategory_raw": "Earnings Call Transcript", "title": "Transcript of the earnings call"}, "earnings_call", "know"),
    ({"category_raw": "Company Update", "subcategory_raw": "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent", "title": "Resignation of Chief Financial Officer"}, "management_change", "act"),
    ({"category_raw": "Company Update", "subcategory_raw": "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent", "title": "Appointment of Secretarial Auditor"}, "unclassified", "routine"),
    ({"category_raw": "Insider Trading / SAST", "subcategory_raw": "Trading Window", "title": "Closure of Trading Window"}, "unclassified", "routine"),
    ({"category_raw": "Company Update", "subcategory_raw": "Credit Rating", "title": "CRISIL downgrades long-term rating to AA-"}, "credit_rating", "act"),
    ({"category_raw": "Company Update", "subcategory_raw": "Credit Rating", "title": "ICRA reaffirms rating"}, "credit_rating", "routine"),
    ({"category_raw": "Company Update", "subcategory_raw": "Acquisition", "title": "Acquisition of 100% stake in XYZ Pvt Ltd"}, "M&A", "act"),
    ({"category_raw": "Company Update", "subcategory_raw": "Allotment of ESOP / ESPS", "title": "Allotment of equity shares under ESOP"}, "unclassified", "routine"),
    ({"category_raw": "Company Update", "subcategory_raw": "Analyst / Investor Meet - Intimation", "title": "Schedule of analyst meet"}, "investor_meetings", "routine"),
    ({"category_raw": "Insider Trading / SAST", "subcategory_raw": "Disclosure of pledged shares", "title": "Creation of pledge by promoter"}, "pledging", "act"),
    ({"category_raw": "Company Update", "subcategory_raw": "Award of Order / Receipt of Order", "title": "Receipt of order worth Rs 450 crore"}, "press_release", "know"),
    ({"category_raw": "Corp. Action", "subcategory_raw": "Dividend", "title": "Record date for interim dividend"}, "dividend", "know"),
    ({"category_raw": "Board Meeting", "subcategory_raw": "Board Meeting Intimation", "title": "Board meeting to consider financial results - Intimation"}, "results", "routine"),
    ({"category_raw": "Company Update", "subcategory_raw": "Newspaper Publication", "title": "Copy of newspaper publication of financial results"}, "results", "routine"),
    ({"category_raw": "Company Update", "subcategory_raw": "Litigation", "title": "GST demand order of Rs 120 crore"}, "litigation", "act"),
]


@pytest.mark.parametrize("item,cat,tier", CASES)
def test_taxonomy(item, cat, tier):
    c = taxonomy.classify(item)
    assert c == cat
    s, why = taxonomy.score(item, c)
    assert taxonomy.tier(s) == tier, (s, why)


def test_alert_scan():
    rows = [[f"2026-10-{i:02d}", 100.0, 1000] for i in range(1, 26)]
    rows.append(["2026-10-26", 106.0, 3000])
    out = alerts.scan({"X": rows}, {"price_pct": 5, "volume_x": 2})
    assert out and out[0]["why"] == ["price", "volume"]
    assert alerts.scan({"X": rows}, {"price_pct": 7, "volume_x": 4}) == []


def test_results_math():
    raw = {"unit": "lakh", "revenue": [10000, 9000, 8000], "other_income": [100, 100, 100], "finance_costs": [50, 50, 50],
           "depreciation": [200, 200, 200], "pbt_before_exceptional": [1500, 1300, 1000], "pbt": [1500, 1300, 900],
           "pat": [1100, 950, 700]}
    rows, margin = enrich.headline_numbers(raw)
    rev = rows[0]
    assert rev["cur"] == 100.0 and rev["qoq"] == 11.1 and rev["yoy"] == 25.0
    eb = rows[1]
    assert eb["cur"] == 16.5
    assert margin == 16.5
    chk = enrich.crosscheck(rows, [{"label": "Q2 FY27", "revenue": 100.5, "pat": 11}])
    assert chk["status"] == "match"


def test_parse_json():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('Sure: {"a": [1,2]} done') == {"a": [1, 2]}

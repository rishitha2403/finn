import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import run, sources


def fake_prices(symbols, days=180):
    out = {}
    for k, s in enumerate(symbols):
        rows = []
        for i in range(60):
            c = 100 + i * 0.1
            v = 1000
            if i == 59 and k == 0:
                c = 110
                v = 5000
            rows.append([f"2026-08-{(i % 28) + 1:02d}", c, v])
        out[s] = rows
    return out


def fake_ann(pf, days, log):
    items = [
        {"id": "bse:1", "symbol": pf[0]["symbol"], "ts": "2099-01-01T10:00:00+05:30", "source": "BSE",
         "title": "Unaudited financial results for the quarter ended September 30, 2026", "subject": "",
         "category_raw": "Result", "subcategory_raw": "Financial Results", "critical": False, "url": None, "url_alt": None},
        {"id": "bse:2", "symbol": pf[1]["symbol"], "ts": "2099-01-01T09:00:00+05:30", "source": "BSE",
         "title": "Closure of trading window", "subject": "", "category_raw": "Insider Trading / SAST",
         "subcategory_raw": "Trading Window", "critical": False, "url": None, "url_alt": None},
    ]
    return items, {p["symbol"]: "bse:1" for p in pf}


def test_run_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "DATA", tmp_path)
    monkeypatch.setattr(sources, "prices", fake_prices)
    monkeypatch.setattr(sources, "announcements", fake_ann)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["run"])
    run.main()
    filings = json.loads((tmp_path / "filings.json").read_text())
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert [f["tier"] for f in filings] == ["act", "routine"]
    assert meta["counts"]["act"] == 1
    assert len(meta["portfolio"]) >= 15
    run.main()
    again = json.loads((tmp_path / "filings.json").read_text())
    assert len(again) == 2

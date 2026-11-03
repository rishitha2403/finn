import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import llm, net
from tests import fake_screener


class Resp:
    def __init__(self, text="", content=b"", status=200, js=None):
        self.text = text
        self.content = content
        self.status_code = status
        self._js = js

    def raise_for_status(self):
        pass

    def json(self):
        return self._js


EXTRACT = {
    "call_quarter": "Q2 FY27",
    "guidance": [{"metric": "revenue_growth", "statement": "15-17% revenue growth in FY27", "quote": "we expect 15 to 17 percent",
                  "low": 15, "high": 17, "unit": "%", "period": "FY27", "speaker": "CFO"},
                 {"metric": "capex", "statement": "Capex of 400 cr in FY27", "quote": "capex around 400 crore",
                  "low": 400, "high": 400, "unit": "cr", "period": "FY27", "speaker": "CEO"}],
    "business": {"what": "Widgets for utilities", "segments": [{"name": "Widgets", "share_pct": 80, "comment": "core"}]},
    "tone": "Confident; order book at a record.",
    "analyst_pressure": ["working capital"],
}
SYNTH = {"read": ["a 1", "b 2", "c 3"], "credibility": {"score": "mixed", "why": "x"}, "qualitative": [],
         "narrative_vs_numbers": [], "bull": ["1"], "bear": ["2"], "watch_next": ["3"]}


def fake_get(url, tries=3, timeout=20, **kw):
    if "screener.in" in url:
        return Resp(text=fake_screener.page())
    return Resp(content=b"%PDF-1.4 fake")


def fake_post(url, params=None, json=None, timeout=None):
    prompt = json["contents"][0]["parts"][-1]["text"]
    out = SYNTH if "60 seconds" in prompt else EXTRACT
    import json as j
    return Resp(status=200, js={"candidates": [{"content": {"parts": [{"text": j.dumps(out)}]}}],
                                "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 200}})


def test_api_stages(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("FINN_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(net, "get", fake_get)
    monkeypatch.setattr(llm.requests, "post", fake_post)
    from api.research import handler

    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/api/research"

    n = json.loads(urllib.request.urlopen(f"{base}?symbol=fake&stage=numbers").read())
    assert n["symbol"] == "FAKE" and n["snapshot"]["latest_quarter"] == "Q2 FY27"
    assert "_qs" not in n

    g = json.loads(urllib.request.urlopen(f"{base}?symbol=FAKE&stage=guidance").read())
    assert g["transcripts_found"] == 4
    assert len(g["track"]) == 8
    assert g["track"][0]["verdict"] in ("on track", "behind", "ahead")
    assert g["usage"]["calls"] + g["usage"]["cache_hits"] == 4

    req = urllib.request.Request(f"{base}?symbol=FAKE&stage=synthesis", data=json.dumps(g).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    s = json.loads(urllib.request.urlopen(req).read())
    assert s["read"][0] == "a 1"

    try:
        urllib.request.urlopen(f"{base}?symbol=..%2F&stage=numbers")
        assert False
    except urllib.error.HTTPError as e:
        assert e.code == 400
    srv.shutdown()

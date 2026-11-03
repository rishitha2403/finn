import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import llm, research, screener


def _reply(h, code, obj):
    body = json.dumps(obj, ensure_ascii=False).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", "public, s-maxage=21600, stale-while-revalidate=86400" if code == 200 else "no-store")
    h.send_header("Access-Control-Allow-Origin", "*")
    h.end_headers()
    h.wfile.write(body)


def _run(h, stage, symbol, payload=None):
    try:
        symbol = screener.clean_symbol(symbol)
    except ValueError as e:
        return _reply(h, 400, {"error": str(e)})
    llm.ledger.reset()
    try:
        if stage == "numbers":
            out = research.stage_numbers(symbol)
        elif stage == "guidance":
            if not llm.available():
                return _reply(h, 503, {"error": "The server has no GEMINI_API_KEY, so transcripts can't be read. Numbers still work."})
            out = research.stage_guidance(symbol)
        elif stage == "synthesis":
            if not llm.available():
                return _reply(h, 503, {"error": "The server has no GEMINI_API_KEY."})
            out = research.stage_synthesis(symbol, payload or {})
        else:
            return _reply(h, 400, {"error": "stage must be numbers, guidance or synthesis"})
    except screener.NotFound as e:
        return _reply(h, 404, {"error": f"No financials found for {symbol} on screener.in. Check the NSE symbol.", "detail": str(e)})
    except llm.LLMError as e:
        return _reply(h, 502, {"error": f"The model call failed: {e}"})
    except Exception as e:
        traceback.print_exc()
        return _reply(h, 500, {"error": f"{type(e).__name__}: {e}"[:300]})
    out["usage"] = llm.ledger.summary()
    _reply(h, 200, out)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        _run(self, q.get("stage", ["numbers"])[0], q.get("symbol", [""])[0])

    def do_POST(self):
        q = parse_qs(urlparse(self.path).query)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 400_000:
            return _reply(self, 413, {"error": "payload too large"})
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return _reply(self, 400, {"error": "body must be JSON"})
        _run(self, q.get("stage", ["synthesis"])[0], q.get("symbol", [payload.get("symbol", "")])[0], payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

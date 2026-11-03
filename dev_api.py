import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from api.research import handler

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8787"))
    print(f"FINN research API on http://localhost:{port}/api/research?symbol=TCS")
    ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()

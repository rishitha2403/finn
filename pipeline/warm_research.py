import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import research

OUT = ROOT / "web" / "public" / "data" / "research"


def main():
    ap = argparse.ArgumentParser(description="Prepare research memos ahead of time so the demo opens instantly")
    ap.add_argument("symbols", nargs="*")
    a = ap.parse_args()
    syms = a.symbols
    if not syms:
        cfg = json.loads((ROOT / "pipeline" / "portfolio.json").read_text())
        syms = cfg.get("research_demo", [])
    OUT.mkdir(parents=True, exist_ok=True)
    for s in syms:
        print(f"{s} ...", flush=True)
        try:
            r = research.full(s)
        except Exception as e:
            print(f"  failed: {e}")
            continue
        (OUT / f"{r['symbol']}.json").write_text(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
        u = r.get("usage", {})
        print(f"  ok; story: {'yes' if r.get('synthesis') else r.get('story_error')}; calls {u.get('calls')}, ${u.get('usd_if_paid')} at paid rates")
    index = sorted(p.stem for p in OUT.glob("*.json") if p.stem != "index")
    (OUT / "index.json").write_text(json.dumps(index))


if __name__ == "__main__":
    main()

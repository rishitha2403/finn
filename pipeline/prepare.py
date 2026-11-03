import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import doctor


def step(title):
    print(f"\n=== {title} ===", flush=True)


def run(mod, *args):
    r = subprocess.run([sys.executable, "-m", mod, *args], cwd=ROOT)
    return r.returncode == 0


def main():
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey and set it first:")
        print("  macOS/Linux:  export GEMINI_API_KEY=your_key")
        print("  Windows:      set GEMINI_API_KEY=your_key      (PowerShell: $env:GEMINI_API_KEY=\"your_key\")")
        sys.exit(1)

    step("1/3  Checking every data source")
    ok = {
        "prices": doctor.check("Yahoo Finance prices", doctor.yahoo),
        "bse": doctor.check("BSE announcements", doctor.bse),
        "nse": doctor.check("NSE announcements (fallback)", doctor.nse),
        "screener": doctor.check("screener.in fundamentals", doctor.scr),
        "gemini": doctor.check("Gemini API", doctor.gem),
    }
    if not ok["gemini"]:
        print("\nGemini failed. Check the key, or set FINN_MODEL_FAST / FINN_MODEL_SMART to models your key can use.")
        sys.exit(1)
    if not (ok["bse"] or ok["nse"]):
        print("\nNeither BSE nor NSE answered. Try another network (phone hotspot often works), then run this again.")
        sys.exit(1)
    if not ok["prices"]:
        print("\nPrices failed; the brief will still work, but price alerts will be empty. Continuing.")
    if not ok["screener"]:
        print("\nscreener.in failed; skipping research memos. The Brief and Watch tabs still work.")

    step("2/3  Building the portfolio brief (filings, prices, summaries)")
    if not run("pipeline.run"):
        print("The pipeline run failed. Copy the error above and send it back.")
        sys.exit(1)

    if ok["screener"]:
        step("3/3  Preparing the demo research memos")
        run("pipeline.warm_research")

    data = ROOT / "web" / "public" / "data"
    files = sorted(p.relative_to(data).as_posix() for p in data.rglob("*.json"))
    print(f"\nWrote {len(files)} data files: {', '.join(files[:8])}{' …' if len(files) > 8 else ''}")
    print("\nNext:")
    print("  1. python dev_api.py            (leave running)")
    print("  2. cd web && npm install && npm run dev   (in a second terminal)")
    print("  3. Open the printed URL, check Brief, Watch and Research, then push to GitHub.")


if __name__ == "__main__":
    main()

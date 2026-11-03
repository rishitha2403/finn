# FINN

A phone-first investing assistant for an 18-stock Indian portfolio. It does two jobs:

- **Brief (push).** Every few hours it pulls each holding's BSE filings and end-of-day prices, decides which few need the investor, and sets the rest aside. Results filings arrive as a Revenue / EBITDA / PBT / PAT table with QoQ and YoY. Management changes arrive with the incoming person's profile. Moves past the investor's own price and volume lines show up at the top, and a Telegram message goes out when something needs attention.
- **Research (pull).** Type any NSE symbol. FINN pulls ten years of reported financials, reads the last four earnings-call transcripts, and checks every number management promised against what was reported. The memo opens with that track record, then the numbers, trajectory, balance sheet, cash quality and a bull/bear case.

Live app: `<your Vercel URL>` · Build history: `<link to AI chat exports>`

## The idea behind the interface

An investor's problem is not finding filings; it is ignoring most of them safely. So the home screen leads with what FINN *buried*: "47 filings since you last looked. 3 need you; 44 set aside." Every set-aside filing is one tap away, grouped by type, so nothing is hidden, only ranked.

The default window is "since you last looked", not a fixed 24 hours, because that is the question someone opening the app actually has. Items that need action are cards you can tick off; everything else is a plain list.

For alerts, a threshold slider means little in the abstract. The Watch screen replays the last 60 sessions against your lines and tells you how often they would have fired ("about 2.4 a week"), so you can tune noise before it reaches your phone.

Research is a memo, not a chat. A portfolio manager wants a page they can scan in a minute, with every claim traceable to a number or a transcript quote. The most valuable section, promised vs delivered, goes first.

## How it works

```
GitHub Actions (5×/day)                         Vercel
┌──────────────────────────────┐   commit    ┌─────────────────────────────┐
│ pipeline/run.py              │ ──────────▶ │ web/ (React, static)        │
│  yfinance  → eod.json        │  data/*.json│  Brief · Watch · Research   │
│  BSE (NSE fallback) filings  │             │                             │
│  rules classify + score      │             │ api/research.py (Python)    │
│  Gemini Flash-Lite: one-line │             │  stage 1 numbers  (no LLM)  │
│    summaries, results table, │             │  stage 2 guidance (Lite ×4) │
│    management profiles       │             │  stage 3 synthesis (Flash)  │
│  Telegram push               │             └─────────────────────────────┘
└──────────────────────────────┘
```

**Classification is rules first, model second.** BSE already tags each filing with a category and subcategory. A rule table in `core/taxonomy.py` maps those plus the headline into the 17 categories from the brief and gives each a materiality score (a CFO exit scores higher than a company-secretary change; a rating downgrade higher than a reaffirmation). This costs nothing and is predictable. The model only sees filings that scored high enough to be worth a sentence, and its "is this material?" answer nudges the score up or down by a few points rather than deciding it.

**Numbers come from code, words come from the model.** For results, the model copies the printed line items (revenue, other income, finance costs, depreciation, PBT, PAT) for three columns; code computes EBITDA and the QoQ / YoY changes, then cross-checks revenue against screener.in. If they disagree by more than 2%, the extraction is re-run on the stronger model. In research, every ratio, CAGR, cash-conversion figure and guidance verdict that can be computed is computed in Python. The model gets those results as input and writes prose around them.

**Guidance is checked, not summarised.** Each transcript yields structured commitments (metric, range, period). Where the metric is revenue growth, margin or profit growth and the period is a fiscal year or quarter, code looks up the reported figure and labels it met / missed, or on track / behind for a year still in progress (using the year-to-date quarters against the same quarters last year). The model only judges commitments code can't check, such as capex or order book.

**Model routing.** Gemini 3.5 Flash-Lite does bulk extraction from PDFs (it accepts PDFs directly, so there is no OCR or chunking step). Gemini 3.8 Flash does the one synthesis call per company and the rare results re-check. Both are on the free tier. Every call is cached on disk by a hash of the prompt and PDF, filings already processed are never re-sent, and each run records its token use and what it would cost at paid rates (shown in the app footer). A full research memo is five model calls: four cheap extractions and one synthesis.

**Primary sources only on the research side.** The model reads the company's transcripts and is told not to use anything else it knows. Financials come from screener.in's standardised tables, which are built from the company's own filings. No news, broker notes or search.

## What I left out, on purpose

- **LinkedIn scraping.** It breaks LinkedIn's terms and gets blocked quickly. SEBI already requires a "brief profile" of every newly appointed director or KMP inside the disclosure itself, so FINN extracts that, and adds a LinkedIn search link.
- **Annual-report PDFs in the live path.** They run 200–400 pages; reading them on every request would blow the 60-second function limit and the free quota. The multi-year financials come from the same filings via screener.in. Annual-report reading is the first thing I would add as an offline job.
- **Chat as the main interface.** Typing questions on a phone is slower than scanning a page already built around the questions an investor asks about every company. A free-form "ask the transcripts" box is a reasonable next step, not the core.
- **Accounts and a database.** Preferences live in the browser; data lives in JSON files committed by the pipeline. Fine for one investor, wrong for a team.

## Known limits

- In-app alert thresholds are per browser. The Telegram push uses the server defaults in `pipeline/alerts.py`.
- BSE, NSE and screener.in are scraped. If GitHub's runners get blocked, run the pipeline locally and push (below).
- Research on a company without transcripts on screener.in shows the numbers sections only.
- Banks and NBFCs: EBITDA and working-capital days are marked not meaningful rather than forced.

## Run it locally

```bash
pip install -r pipeline/requirements.txt
export GEMINI_API_KEY=...            # free key from aistudio.google.com
python -m pipeline.prepare           # checks every source, then builds the brief and demo memos
                                     # (or step by step: pipeline.doctor, pipeline.run, pipeline.warm_research)
python dev_api.py &                  # research API on :8787
cd web && npm install && npm run dev # app on :5173
```

## Deploy

1. Push the repo to GitHub.
2. Import it on vercel.com. No settings to change; `vercel.json` covers the build. Add `GEMINI_API_KEY` as an environment variable.
3. On GitHub, add `GEMINI_API_KEY` (and optionally `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) under Settings → Secrets → Actions, and `FINN_APP_URL` under Variables. Run the "FINN daily run" workflow once by hand.

## Repo map

| Path | What it does |
|---|---|
| `core/taxonomy.py` | Filing categories, materiality scores, tiers |
| `core/screener.py` | Fetches and parses a company page on screener.in |
| `core/fundamentals.py` | All research numbers: TTM, CAGRs, D/E, cash conversion, FCF estimate, signals |
| `core/guidance.py` | Transcript extraction, guidance verification, synthesis prompt |
| `core/llm.py` | Gemini client with model tiers, fallbacks, disk cache and usage ledger |
| `pipeline/run.py` | The scheduled job: prices, filings, enrichment, push |
| `pipeline/enrich.py` | Results table, management profile, one-line summaries |
| `api/research.py` | Three-stage research endpoint (Vercel Python function) |
| `web/src/views/` | Brief, Watch, Research screens |
| `tests/` | 29 tests: parsing, classification, guidance verdicts, results maths, the API end to end with mocked sources |

`python -m pytest` runs the tests without network access or an API key.

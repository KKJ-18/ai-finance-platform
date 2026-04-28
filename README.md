# AI Finance Platform

> Multi-source intelligence platform for U.S. and international banks.
> Combines market data (yfinance) with SEC filings (10-K / 10-Q) — extracting
> the **MD&A** and **Risk Factors** sections for downstream NLP analysis.

**Author:** Jordan KAMSU-KOM
**Course:** The Future of AI for Finance and Accounting — Imagine (Johns Hopkins)
**Lesson 3 — Code Technical Exercise**

---

## Why this platform

Lesson 2 covered five U.S. money-center banks with price data only. This
platform extends that work in two directions:

1. **Wider universe** — money-center, regional, European, Canadian, Asian
   banks plus reference ETFs.
2. **Unstructured data** — adds a SEC EDGAR pipeline that downloads 10-K
   and 10-Q filings and extracts the narrative sections (MD&A, Risk
   Factors) that drive most of the qualitative signal in bank analysis.

The goal is to support analyst workflows where the question is not "how
correlated are these stocks?" but "what is *management* saying, and how is
it changing year-over-year?"

---

## Project structure

```
ai-finance-platform/
├── config/universe.yaml            # tickers + CIKs + categories
├── src/
│   ├── prices/                     # yfinance pipeline (Lesson 2 refactor)
│   ├── filings/                    # SEC EDGAR + MD&A/Risk parser
│   ├── analytics/                  # correlations, sentiment, diff
│   └── viz/                        # charts and dashboards
├── scripts/
│   ├── run_prices.py               # end-to-end prices analysis
│   └── run_filings.py              # end-to-end filings analysis
├── data/                           # local cache (gitignored)
└── tests/
```

---

## Quickstart

```bash
pip install -r requirements.txt

# 1. Prices — 5y normalized chart + correlation matrix
python scripts/run_prices.py

# 2. Filings — download latest 10-K for JPM and extract sections
python scripts/run_filings.py --ticker JPM --form 10-K
```

---

## Data sources

| Source | What | Auth |
|---|---|---|
| Yahoo Finance (`yfinance`) | Daily adjusted close, 5y | None |
| SEC EDGAR (`data.sec.gov`) | 10-K, 10-Q filings | User-Agent header |

SEC EDGAR is free but requires a descriptive User-Agent. Set yours in
`config/universe.yaml` or via the `SEC_USER_AGENT` environment variable.

---

## License

MIT — for educational use.

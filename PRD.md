# Product Requirements Document — AI Finance Platform

**Author:** Jordan KAMSU-KOM
**Course:** The Future of AI for Finance and Accounting — Imagine (Johns Hopkins)
**Lesson 3 — Code Technical Exercise**
**Version:** 0.2 (Lesson 3 release)

---

## 1. Problem statement

Bank equity analysts spend the majority of their time reading. A single
10-K can run 200+ pages; the U.S. money-center group alone produces
~5,000 pages of MD&A and Risk Factors per fiscal year, and many more
once 10-Qs are added. Most of that text is **recycled boilerplate**:
the genuine signal — new risks, shifting tone, regulatory changes —
sits in a small fraction of paragraphs that change year over year.

Lesson 2 covered the **quantitative** side of bank coverage (price
correlations across the U.S. money-center group). It did not address
the **qualitative** side, which is where most of the analyst time is
spent and where the biggest ROI for AI exists today.

The Lesson 3 platform is the qualitative companion: it ingests SEC
filings, isolates the narrative sections that matter, and surfaces the
*delta* between this year's filing and last year's.

## 2. Target users

| User                  | Primary need                                                    |
|-----------------------|-----------------------------------------------------------------|
| **Sell-side analyst** | Faster turnaround on 10-K/10-Q reading; comparative tone scoring |
| **Risk officer**      | Detection of new risk factors disclosed by peers                 |
| **Portfolio manager** | Quick screen of sector-wide tone before earnings season          |
| **Compliance**        | Audit trail of disclosure language drift                         |

## 3. Scope (v0.2)

### In scope

* Ingestion of public market data for a configurable bank universe
  (`yfinance`, daily adjusted close, 5-year history).
* Ingestion of SEC EDGAR filings (10-K and 10-Q) with a configurable
  rate-limited downloader and on-disk cache.
* Section extraction for **Item 1A. Risk Factors** and **Item 7. MD&A**
  on 10-Ks, plus their 10-Q equivalents.
* Lexical sentiment scoring (Loughran-McDonald-style finance lexicon).
* Year-over-year paragraph-level diff with fuzzy matching.
* CLI scripts for prices, filings, and YoY diffs.
* Exportable artefacts (PNG charts, CSV tables, plain-text section
  extracts) for downstream consumption.

### Out of scope (deferred to v1.0)

* Foreign filings (20-F, 6-K, non-EDGAR regulators).
* Transformer-based sentiment (FinBERT, Claude, GPT). The current
  lexical scorer is the v0.2 baseline; the interface
  (`score_sentiment(text)`) is stable so the upgrade is one-line.
* Web dashboard (Streamlit). All v0.2 outputs are file-based.
* RAG over filings (semantic Q&A on extracted text).
* Real-time event monitoring (8-K parser).

## 4. Functional requirements

| #  | Requirement                                                   | Acceptance criterion                                               |
|----|---------------------------------------------------------------|--------------------------------------------------------------------|
| F1 | Universe configurable via YAML, no code changes               | New ticker added in `universe.yaml` is picked up by all CLIs       |
| F2 | Compliant SEC EDGAR access                                    | All requests carry a User-Agent; throttle ≤ 5 req/s                |
| F3 | 10-K Risk Factors extraction                                  | Returns ≥ 50,000 chars on the 5 money-center banks; no overlap with MD&A |
| F4 | 10-K MD&A extraction                                          | Returns ≥ 200,000 chars on the 5 money-center banks                 |
| F5 | Sentiment polarity                                            | Risk Factors polarity < 0 on all sample banks                       |
| F6 | YoY paragraph diff                                            | Surfaces ≥ 1 net-new paragraph for any bank where 2 years are available |
| F7 | All outputs reproducible from `pip install -r requirements.txt` + 3 CLI calls | Fresh-clone smoke test passes                                       |

## 5. Non-functional requirements

| #   | Requirement              | Target                                                                                |
|-----|--------------------------|---------------------------------------------------------------------------------------|
| NF1 | Throughput               | A full sector-wide run (5 banks × 1 filing) completes in < 60 s on a residential connection |
| NF2 | Cache discipline         | Re-running the same CLI hits cache, no re-downloads                                   |
| NF3 | Auditability             | Every extracted section is persisted as plain text under `data/extracts/`             |
| NF4 | Determinism              | Same inputs produce identical outputs (lexical scorer, set diff)                     |
| NF5 | Failure isolation        | One bank failing extraction does not break the rest of the run                       |
| NF6 | No secrets in repo       | `.gitignore` excludes `data/`, `.env`, all credential files                           |

## 6. Architecture

```
                                   ┌──────────────────────┐
                                   │  config/universe.yaml│
                                   │  (tickers + CIKs)    │
                                   └──────────┬───────────┘
                                              │
                ┌─────────────────────────────┼──────────────────────────────┐
                │                             │                              │
        ┌───────▼─────────┐         ┌─────────▼────────┐          ┌──────────▼──────────┐
        │ src/prices/     │         │ src/filings/     │          │ src/analytics/      │
        │  yfinance       │         │  EdgarClient     │          │  correlations       │
        │  (Lesson 2)     │         │  parser (MD&A,   │          │  sentiment          │
        │                 │         │   Risk Factors)  │          │  diff (YoY)         │
        └────────┬────────┘         └─────────┬────────┘          └──────────┬──────────┘
                 │                            │                              │
                 └─────────────┬──────────────┴──────────────┬───────────────┘
                               │                             │
                       ┌───────▼────────┐           ┌────────▼─────────┐
                       │ src/viz/       │           │ scripts/         │
                       │  charts        │           │  run_prices      │
                       └───────┬────────┘           │  run_filings     │
                               │                    │  run_diff        │
                               │                    └────────┬─────────┘
                               └───────────┬─────────────────┘
                                           │
                                  ┌────────▼─────────┐
                                  │ data/outputs/    │
                                  │  PNGs, CSVs      │
                                  │ data/extracts/   │
                                  │  plain-text      │
                                  └──────────────────┘
```

### Module responsibilities

| Module             | Responsibility                                                |
|--------------------|---------------------------------------------------------------|
| `src/config`       | Universe loader + `Bank` dataclass                            |
| `src/prices`       | `yfinance` wrapper, returns, normalised series, summary stats |
| `src/filings/edgar`| SEC EDGAR client (throttled, cached, paginated)               |
| `src/filings/parser`| HTML/iXBRL → text → MD&A / Risk Factors                       |
| `src/analytics/correlations` | Off-diagonal correlation summary                    |
| `src/analytics/sentiment` | Loughran-McDonald-style polarity score                  |
| `src/analytics/diff` | Paragraph-level YoY diff with fuzzy matching                 |
| `src/viz/charts`   | Matplotlib + seaborn helpers                                  |

## 7. Data sources

| Source                  | What                              | Auth                     |
|-------------------------|-----------------------------------|--------------------------|
| Yahoo Finance (`yfinance`) | Daily adjusted close, 5y         | None                     |
| SEC EDGAR (`data.sec.gov`) | 10-K, 10-Q filings + indices    | Descriptive User-Agent   |

Compliance with SEC fair-use rules: every request carries a configured
User-Agent and the client throttles itself to ≤ 5 requests / second
(SEC's published cap is 10 req/s).

## 8. Success metrics

| Metric                                | Target               |
|---------------------------------------|----------------------|
| Coverage (% of universe extractable)   | ≥ 90 %               |
| MD&A extraction precision (manual spot-check on 5 banks) | ≥ 80 % |
| Risk Factors polarity (signal sanity)  | < 0 on all banks     |
| Time from `pip install` to first chart | < 5 minutes          |
| Lines of code                          | < 1,500 (excl. tests) |

## 9. Roadmap

### v0.2 (current — Lesson 3 deliverable)
* 5 money-center banks fully working end-to-end
* MD&A + Risk Factors extraction
* Lexical sentiment + YoY diff

### v0.3 (next — Lesson 4 candidate)
* Replace lexical sentiment with **FinBERT** or **Claude API** scoring
* Add **8-K event detection** (M&A, earnings, leadership changes)
* Streamlit dashboard

### v1.0 (production)
* Full universe coverage (regional, European 20-F, Canadian regulators)
* RAG layer for natural-language queries on filings
* Backtest framework: does negative MD&A polarity predict drawdown?
* Database backend (DuckDB) instead of files

## 10. Risks and mitigations

| Risk                                                   | Mitigation                                                         |
|--------------------------------------------------------|--------------------------------------------------------------------|
| SEC blocks the IP for rate-limit violations             | Throttle to 5 req/s; descriptive User-Agent; on-disk cache         |
| Issuer-specific HTML formatting breaks the parser       | Two-tier anchor list (primary "Item X." + fallback heading) + heading-position filter |
| Lexical sentiment misses sarcasm / context              | Documented as a baseline; v0.3 will replace with Transformer scoring |
| YoY diff inflated by minor edits                        | Fuzzy signature (first 80 normalised chars); MIN_WORDS = 25 filters bullets |
| Public repo accidentally leaks data                     | `.gitignore` excludes `data/`, `.env`, all credentials             |

## 11. Open questions

1. Do we keep the lexical scorer as a permanent baseline, or fully
   replace it with FinBERT in v0.3?
2. Should the YoY diff cluster near-duplicates with cosine similarity
   (true edit detection) or stay set-based?
3. Should we backtest sentiment vs. price action before adding more
   features?

# AI Finance Platform — Lesson 3 Write-up

**Author:** Jordan KAMSU-KOM
**Course:** The Future of AI for Finance and Accounting — Imagine (Johns Hopkins)
**Lesson 3 — Code Technical Exercise**
**Repo:** https://github.com/KKJ-18/ai-finance-platform

---

## What I built

A two-source intelligence platform for U.S. and international banks.
**Lesson 2** covered five money-center banks with price correlations
only. **Lesson 3** keeps that as one module and adds a SEC EDGAR
pipeline that ingests 10-K / 10-Q filings, isolates the **MD&A** and
**Item 1A. Risk Factors** narrative sections, and runs three layers of
analysis:

1. **Lexical sentiment** scoring (Loughran-McDonald-style finance lexicon)
2. **Cross-bank comparison** of polarity per section
3. **Year-over-year paragraph diff** that surfaces newly added or
   removed risk topics — the killer feature of the platform

The whole thing is driven by a single YAML universe file (24 banks
across U.S. money-center, regional, trust/custody, European, Canadian,
plus reference ETFs). Three CLIs cover the workflows:

```bash
python scripts/run_prices.py  --category money_center_us
python scripts/run_filings.py --category money_center_us --form 10-K
python scripts/run_diff.py    --ticker   JPM             --section risk
```

## Headline result

Running the YoY diff on JPM's Risk Factors (2024 10-K → 2025 10-K)
surfaced this **newly disclosed** paragraph:

> *"The rapid development and deployment of advanced technologies,
> including **generative and agentic AI systems**, present a range of
> risks to JPMorganChase's businesses and operations..."*

This is exactly the kind of signal that traditionally requires an
analyst to read both 200-page filings side by side. The platform
isolates it in seconds, with full audit trail (the source paragraph
is persisted on disk and the polarity delta is logged).

Cross-bank polarity (5 money-center banks, FY2025 10-K):

| Bank | MD&A polarity | Risk Factors polarity |
|------|---------------|------------------------|
| JPM  | -0.65         | -0.50                  |
| GS   | -0.70         | -0.39                  |
| MS   | -0.66         | -0.68                  |
| BAC  | -0.53         | -0.58                  |
| C    | -0.64         | -0.72                  |

All polarities are negative as expected (Risk Factors describe risks).
**Citi (-0.72)** has the most negative tone in Risk Factors,
**Goldman (-0.39)** the least — directionally consistent with their
respective business mixes (broad-based consumer credit exposure vs.
trading-heavy, narrower scope).

## Difficulties and how I overcame them

| # | Problem | Resolution |
|---|---------|-----------|
| 1 | **iXBRL filings**: modern 10-Ks are XML-wrapped XHTML, not pure HTML. BeautifulSoup raised warnings. | Suppressed `XMLParsedAsHTMLWarning`; parser still handles content correctly. |
| 2 | **Multiple tables of contents**: JPM has 3 different TOCs that all repeat "Item 7. Management's Discussion." Naive regex caught the TOC, not the body (395 chars instead of 1M). | Added a heading-position filter (`_is_heading_position`) that requires the anchor to be preceded by `\n[digits]\n` — true headers satisfy this; cross-references in prose don't. |
| 3 | **Issuer-specific formatting**: MS and Citi don't repeat `Item 1A.` at the body header — they use `Risk Factors` as a standalone heading. | Two-tier anchor list: primary `Item 1A.` regex + fallback `Risk Factors` regex with the same heading filter. |
| 4 | **Section overlap**: With the fallback anchor, MS's Risk Factors was being extended past the start of MD&A. | Added MD&A start positions as upper-bound end-anchors for Risk Factors — leverages the logical document order (1A always precedes 7). |
| 5 | **Pagination**: JPM has 23,781 filings in EDGAR; only the most recent 10-K fits in the `recent` block. The 2024 10-K needed for YoY diff was on a paginated older page. | Walked `submissions.filings.files[]` in `EdgarClient._filings_pages()`; cached each page on disk. |
| 6 | **Diff noise**: First version showed 200% churn (every paragraph "added + removed") because minor edits broke set equality. | Added aggressive `_normalise` (curly quotes, dashes, punctuation, NBSP) + a fuzzy signature mode that matches paragraphs by their first 80 normalised chars. |
| 7 | **Windows encoding**: Python on Windows defaults to cp1252 and choked on the ✓ character in a print statement. | Set `PYTHONIOENCODING=utf-8` in run instructions; documented in README. |

## Are we at AGI now?

**No — and the gap is informative, not just academic.**

What Claude Code did effortlessly in this project:
* Wrote idiomatic Python with proper module boundaries, type hints, and
  docstrings.
* Designed regex strategies for parsing irregular SEC filings with
  context-aware fallbacks.
* Diagnosed problems by reading error traces and proposing targeted
  fixes (the heading-position filter was a clean architectural insight,
  not a brute-force patch).
* Wrote the PRD, the README, and this write-up in coherent English.

What it could **not** do without me in the loop:
* **Decide what was worth building.** The YoY diff is the single most
  valuable feature in this platform. That decision came from a
  conversation about what an analyst's day looks like — domain
  judgment, not code.
* **Decide when to stop tuning.** When MS's Risk Factors overlapped
  with MD&A, I had to call "ship the constraint-based fix and move on"
  rather than chase a perfect parser for every edge case.
* **Anticipate what the prof would weight.** The instinct to write the
  PRD before the code, to make the universe.yaml configurable, and to
  add the YoY diff as the "killer feature" all came from reading the
  assignment instructions critically.
* **Recognize when an output is wrong.** The platform happily produced
  775,000 chars of Risk Factors for Morgan Stanley before I noticed
  the content was the same as MD&A. AGI would catch that without being
  told.

What this maps to in the lecture's framing: Transformers solved the
*context problem* — they made it possible to build this platform in
Python in a few hours instead of months. They have **not** solved the
*judgment problem* (what is worth doing, what is good enough, what is
wrong). Lesson 2's lecture made the same point about embeddings:
having vectors is not having understanding. Today's tools are
extraordinary force multipliers for an operator with judgment, and
unreliable when used without one.

If "AGI" means a system that can deliver this entire project from a
one-line prompt, including the architectural choices and stop-tuning
decisions, then no — we are not there. If it means a system that
makes a competent operator dramatically faster and broader, then yes,
we are already living in that world, and have been for ~18 months.

## What I would do next

* Replace the lexical sentiment scorer with **FinBERT** or **Claude API**
  scoring (interface is already stable: `score_sentiment(text) -> dict`).
* Add an **8-K event detector** for real-time disclosure monitoring.
* Backtest: does a sharp negative shift in MD&A polarity precede
  drawdown in the bank's stock?
* RAG layer over the extracted sections so analysts can ask
  "what changed in JPM's market risk discussion this year?" in natural
  language.

---

*Submitted as part of the Lesson 3 Code Technical Exercise.*

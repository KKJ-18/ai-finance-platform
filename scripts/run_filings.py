"""
End-to-end SEC filings analysis.

Pipeline:
    1. Resolve target banks (single ticker or whole category).
    2. For each: locate latest 10-K (or 10-Q) on EDGAR, download HTML.
    3. Extract MD&A and Risk Factors sections.
    4. Score each section with the financial sentiment lexicon.
    5. Save per-ticker text dumps and a comparative CSV/PNG.

Usage:
    python scripts/run_filings.py --ticker JPM
    python scripts/run_filings.py --category money_center_us --form 10-K
    python scripts/run_filings.py --ticker JPM --form 10-Q --n-recent 4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import banks_by_category, find  # noqa: E402
from src.filings.edgar import EdgarClient  # noqa: E402
from src.filings.parser import parse_file  # noqa: E402
from src.analytics.sentiment import score_sentiment  # noqa: E402
from src.viz.charts import sentiment_bar  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "outputs"
TEXTS_DIR = REPO_ROOT / "data" / "extracts"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TEXTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run SEC filings analysis.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ticker", help="Single ticker (e.g. JPM).")
    g.add_argument("--category", help="Universe category (e.g. money_center_us).")
    p.add_argument("--form", default="10-K", choices=["10-K", "10-Q"])
    p.add_argument(
        "--n-recent",
        type=int,
        default=1,
        help="How many recent filings per ticker (default 1 = latest).",
    )
    return p.parse_args()


def resolve_banks(args: argparse.Namespace):
    if args.ticker:
        return [find(args.ticker)]
    return [b for b in banks_by_category(args.category) if b.has_sec_filings]


def main() -> None:
    args = parse_args()
    banks = resolve_banks(args)
    if not banks:
        raise SystemExit("No SEC-eligible banks selected.")

    client = EdgarClient()
    rows: list[dict] = []

    for bank in banks:
        print(f"\n=== {bank.ticker} ({bank.name}) — CIK {bank.cik} ===")
        refs = client.list_filings(
            bank.cik, bank.ticker, forms=(args.form,), limit=args.n_recent
        )
        if not refs:
            print(f"  No {args.form} found.")
            continue

        for ref in refs:
            print(f"  {ref.form} filed {ref.filing_date} (period {ref.report_date})")
            html_path = client.download(ref)
            sections = parse_file(html_path, ref.form, ref.ticker, ref.report_date)

            # Persist plain-text extracts for downstream NLP / qualitative review
            stem = f"{bank.ticker}_{ref.form}_{ref.report_date}"
            (TEXTS_DIR / f"{stem}__mda.txt").write_text(
                sections.mda, encoding="utf-8"
            )
            (TEXTS_DIR / f"{stem}__risk.txt").write_text(
                sections.risk_factors, encoding="utf-8"
            )

            mda_score = score_sentiment(sections.mda)
            risk_score = score_sentiment(sections.risk_factors)

            print(
                f"    MD&A: {len(sections.mda):>7} chars | "
                f"polarity={mda_score.polarity:+.3f}"
            )
            print(
                f"    Risk: {len(sections.risk_factors):>7} chars | "
                f"polarity={risk_score.polarity:+.3f}"
            )

            rows.append(
                {
                    "ticker": bank.ticker,
                    "name": bank.name,
                    "form": ref.form,
                    "report_date": ref.report_date,
                    "mda_chars": len(sections.mda),
                    "risk_chars": len(sections.risk_factors),
                    "mda_polarity": mda_score.polarity,
                    "risk_polarity": risk_score.polarity,
                    "mda_neg_ratio": mda_score.ratios["negative"],
                    "risk_neg_ratio": risk_score.ratios["negative"],
                    "mda_uncertainty_ratio": mda_score.ratios["uncertainty"],
                }
            )

    if not rows:
        return

    df = pd.DataFrame(rows)
    csv_path = OUT_DIR / f"filings_sentiment_{args.form}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n[OK] {csv_path}")

    # Comparative bar chart on polarity (only if >1 ticker)
    if len(df) > 1:
        chart_df = df.set_index("ticker")[["mda_polarity", "risk_polarity"]]
        png_path = OUT_DIR / f"filings_sentiment_{args.form}.png"
        sentiment_bar(
            chart_df,
            title=f"{args.form} sentiment polarity by bank (MD&A vs Risk Factors)",
            save_to=png_path,
        )
        print(f"[OK] {png_path}")

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()

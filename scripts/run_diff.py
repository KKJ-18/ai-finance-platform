"""
Year-over-year diff on filings.

For a given ticker, downloads the two most recent 10-Ks and surfaces:
    * paragraphs added this year   → what's a NEW concern for management
    * paragraphs removed           → what risks are no longer disclosed
    * polarity drift               → tone shifting more / less negative
    * churn rate                   → how much the section changed overall

Usage:
    python scripts/run_diff.py --ticker JPM
    python scripts/run_diff.py --ticker JPM --form 10-K --section risk
    python scripts/run_diff.py --ticker GS --section both
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import find  # noqa: E402
from src.filings.edgar import EdgarClient  # noqa: E402
from src.filings.parser import parse_file  # noqa: E402
from src.analytics.diff import diff_sections  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "outputs" / "diffs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="YoY filings diff.")
    p.add_argument("--ticker", required=True)
    p.add_argument("--form", default="10-K", choices=["10-K", "10-Q"])
    p.add_argument(
        "--section",
        default="risk",
        choices=["risk", "mda", "both"],
        help="Which section to diff (default: risk).",
    )
    p.add_argument(
        "--max-show",
        type=int,
        default=5,
        help="Max added/removed paragraphs to print to stdout.",
    )
    return p.parse_args()


def truncate(text: str, n: int = 240) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= n else text[:n] + " ..."


def run_one_diff(args, ticker: str, section_key: str):
    bank = find(ticker)
    if not bank.has_sec_filings:
        raise SystemExit(f"{ticker} has no SEC CIK on file.")

    client = EdgarClient()
    refs = client.list_filings(bank.cik, bank.ticker, forms=(args.form,), limit=2)
    if len(refs) < 2:
        raise SystemExit(f"Only {len(refs)} {args.form} found for {ticker}; need 2.")

    current_ref, prior_ref = refs[0], refs[1]
    print(f"\n=== {ticker} | {section_key.upper()} ===")
    print(f"  Current : {current_ref.form} {current_ref.report_date}")
    print(f"  Prior   : {prior_ref.form}   {prior_ref.report_date}")

    current_html = client.download(current_ref)
    prior_html = client.download(prior_ref)

    current_sec = parse_file(
        current_html, current_ref.form, ticker, current_ref.report_date
    )
    prior_sec = parse_file(prior_html, prior_ref.form, ticker, prior_ref.report_date)

    section_label = "Risk Factors" if section_key == "risk" else "MD&A"
    current_text = (
        current_sec.risk_factors if section_key == "risk" else current_sec.mda
    )
    prior_text = prior_sec.risk_factors if section_key == "risk" else prior_sec.mda

    if not current_text or not prior_text:
        print(f"  [skip] empty section in one of the filings")
        return

    diff = diff_sections(
        ticker=ticker,
        section_name=section_label,
        prior_text=prior_text,
        current_text=current_text,
        prior_date=prior_ref.report_date,
        current_date=current_ref.report_date,
    )

    print(f"\n  Paragraphs        : {diff.n_prior}  ->  {diff.n_current}")
    print(f"  Added             : {len(diff.added)}")
    print(f"  Removed           : {len(diff.removed)}")
    print(f"  Kept (unchanged)  : {diff.kept_count}")
    print(f"  Churn rate        : {diff.churn_rate:.1%}")
    print(
        f"  Polarity          : {diff.prior_polarity:+.3f}  ->  "
        f"{diff.current_polarity:+.3f}  (delta {diff.polarity_delta:+.3f})"
    )

    print(f"\n  --- ADDED paragraphs (showing up to {args.max_show}) ---")
    for p in diff.added[: args.max_show]:
        print(f"  + {truncate(p)}")
    if len(diff.added) > args.max_show:
        print(f"  ... ({len(diff.added) - args.max_show} more)")

    print(f"\n  --- REMOVED paragraphs (showing up to {args.max_show}) ---")
    for p in diff.removed[: args.max_show]:
        print(f"  - {truncate(p)}")
    if len(diff.removed) > args.max_show:
        print(f"  ... ({len(diff.removed) - args.max_show} more)")

    # Persist full diff
    stem = f"{ticker}_{args.form}_{section_key}_{prior_ref.report_date}_to_{current_ref.report_date}"
    txt_path = OUT_DIR / f"{stem}.txt"
    with txt_path.open("w", encoding="utf-8") as f:
        f.write(f"# Diff {ticker} {section_label} ({prior_ref.report_date} -> {current_ref.report_date})\n\n")
        f.write(f"## Summary\n{diff.summary()}\n\n")
        f.write(f"## Added ({len(diff.added)} paragraphs)\n\n")
        for p in diff.added:
            f.write(f"+++\n{p}\n\n")
        f.write(f"## Removed ({len(diff.removed)} paragraphs)\n\n")
        for p in diff.removed:
            f.write(f"---\n{p}\n\n")
    print(f"\n  [OK] full diff -> {txt_path}")


def main() -> None:
    args = parse_args()

    sections = ["risk", "mda"] if args.section == "both" else [args.section]
    for sec in sections:
        run_one_diff(args, args.ticker, sec)


if __name__ == "__main__":
    main()

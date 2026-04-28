"""
End-to-end prices analysis — equivalent of Lesson 2's analyse_banques.py
but operating over the full universe defined in config/universe.yaml.

Usage:
    python scripts/run_prices.py
    python scripts/run_prices.py --category money_center_us
    python scripts/run_prices.py --tickers JPM,GS,MS,BAC,C
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script from project root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import all_banks, banks_by_category, find  # noqa: E402
from src.prices.downloader import (  # noqa: E402
    download_prices,
    daily_returns,
    normalized_prices,
    summary_stats,
)
from src.analytics.correlations import (  # noqa: E402
    correlation_matrix,
    summary_stats_corr,
)
from src.viz.charts import (  # noqa: E402
    normalized_chart,
    correlation_heatmap,
)

OUT_DIR = REPO_ROOT / "data" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run prices analysis.")
    p.add_argument(
        "--category",
        default="money_center_us",
        help="Universe category from config/universe.yaml.",
    )
    p.add_argument(
        "--tickers",
        default=None,
        help="Comma-separated tickers (overrides --category).",
    )
    p.add_argument("--years", type=int, default=5, help="Lookback in years.")
    return p.parse_args()


def resolve_tickers(args: argparse.Namespace) -> list[str]:
    if args.tickers:
        return [t.strip().upper() for t in args.tickers.split(",")]
    banks = banks_by_category(args.category)
    if not banks:
        raise SystemExit(f"No banks in category '{args.category}'")
    return [b.ticker for b in banks]


def main() -> None:
    args = parse_args()
    tickers = resolve_tickers(args)

    print(f"Universe : {tickers}")
    print(f"Years    : {args.years}\n")

    prices = download_prices(tickers, years=args.years)
    print(f"Rows     : {len(prices)}")
    print(f"Period   : {prices.index.min().date()} -> {prices.index.max().date()}\n")

    # Normalized chart
    norm = normalized_prices(prices)
    chart_path = OUT_DIR / f"prices_normalized_{args.category}.png"
    normalized_chart(
        norm,
        title=f"Bank universe — {args.years}y normalized price (base 100)",
        save_to=chart_path,
    )
    print(f"[OK] {chart_path}")

    # Correlations
    rets = daily_returns(prices)
    corr = correlation_matrix(rets)
    heat_path = OUT_DIR / f"correlation_{args.category}.png"
    correlation_heatmap(
        corr,
        title=f"Daily-return correlation — {args.years}y",
        save_to=heat_path,
    )
    print(f"[OK] {heat_path}")

    corr_csv = OUT_DIR / f"correlation_{args.category}.csv"
    corr.to_csv(corr_csv)
    print(f"[OK] {corr_csv}")

    # Summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)
    print(summary_stats(prices))

    print("\n" + "=" * 60)
    print("CORRELATION SUMMARY")
    print("=" * 60)
    s = summary_stats_corr(corr)
    print(f"Mean intra-sector : {s['mean']}")
    print(f"Max pair          : {s['max_pair']}  ({s['max']})")
    print(f"Min pair          : {s['min_pair']}  ({s['min']})")


if __name__ == "__main__":
    main()

"""
Price data pipeline — yfinance wrapper with caching and clean DataFrame
shape (DateIndex, ticker columns, adjusted close).

Refactored from Lesson 2's analyse_banques.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import yfinance as yf

from src.config import DATA_DIR


def _cache_path(tickers: Iterable[str], start: datetime, end: datetime) -> Path:
    cache_dir = DATA_DIR / "prices"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = (
        "_".join(sorted(tickers))
        + f"__{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.parquet"
    )
    # Parquet keeps dtypes; if pyarrow not installed fall back to CSV.
    return cache_dir / key


def download_prices(
    tickers: list[str],
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    years: int = 5,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Download daily adjusted close for `tickers` and return a wide DataFrame
    indexed by date with one column per ticker.

    yfinance returns columns sorted alphabetically; we restore the user's
    order. NaN rows (non-overlapping calendars) are dropped.
    """
    if not tickers:
        raise ValueError("tickers must not be empty")

    end = end or datetime.today()
    start = start or end - timedelta(days=years * 365)

    cache = _cache_path(tickers, start, end)
    csv_cache = cache.with_suffix(".csv")

    if use_cache and csv_cache.exists():
        df = pd.read_csv(csv_cache, index_col=0, parse_dates=True)
        return df[tickers].dropna()

    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
    )["Close"]

    # Single-ticker case: yfinance returns a Series.
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])

    df = raw[tickers].dropna()

    if use_cache:
        df.to_csv(csv_cache)

    return df


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns (Pt / Pt-1 − 1), first row dropped."""
    return prices.pct_change().dropna()


def normalized_prices(prices: pd.DataFrame, base: float = 100.0) -> pd.DataFrame:
    """Rebase each series to `base` at the first observation."""
    return prices.divide(prices.iloc[0]).multiply(base)


def summary_stats(prices: pd.DataFrame) -> pd.DataFrame:
    """Total return + annualized vol per ticker, in percent."""
    rets = daily_returns(prices)
    total = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
    vol = rets.std() * (252 ** 0.5) * 100
    return pd.DataFrame(
        {
            "Total return (%)": total.round(1),
            "Annualized vol (%)": vol.round(1),
        }
    )

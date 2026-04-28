"""Return correlations + summary stats."""
from __future__ import annotations

import numpy as np
import pandas as pd


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of daily returns. Drops NaN pairwise."""
    return returns.corr()


def summary_stats_corr(corr: pd.DataFrame) -> dict:
    """Mean off-diagonal correlation, max and min pair."""
    n = corr.shape[0]
    if n < 2:
        return {"mean": None, "max": None, "min": None}

    # Off-diagonal mean: total sum minus diagonal (= n) divided by n*(n-1)
    mean_corr = (corr.values.sum() - n) / (n * (n - 1))

    # Mask the diagonal to find the max/min off-diagonal pair
    mask = np.eye(n, dtype=bool)
    masked = corr.mask(mask)

    max_val = masked.max().max()
    min_val = masked.min().min()

    return {
        "mean": round(float(mean_corr), 3),
        "max": round(float(max_val), 3),
        "max_pair": _find_pair(masked, max_val),
        "min": round(float(min_val), 3),
        "min_pair": _find_pair(masked, min_val),
    }


def _find_pair(df: pd.DataFrame, target: float):
    """Find the (row, col) labels whose value matches `target`."""
    for col in df.columns:
        for row in df.index:
            v = df.at[row, col]
            if pd.notna(v) and abs(v - target) < 1e-9:
                return (row, col)
    return None

"""Plot helpers — all return the (fig, ax) pair so callers can save/show."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def normalized_chart(
    normalized: pd.DataFrame,
    title: str,
    save_to: Optional[Path] = None,
):
    fig, ax = plt.subplots(figsize=(12, 6))
    for col in normalized.columns:
        ax.plot(normalized.index, normalized[col], label=col, linewidth=1.5)

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Index (base 100)")
    ax.axhline(100, color="grey", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    if save_to:
        fig.savefig(save_to, dpi=150)
    return fig, ax


def correlation_heatmap(
    corr: pd.DataFrame,
    title: str,
    save_to: Optional[Path] = None,
):
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        vmin=0.3,
        vmax=1.0,
        square=True,
        cbar_kws={"label": "Correlation"},
        ax=ax,
    )
    ax.set_title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()

    if save_to:
        fig.savefig(save_to, dpi=150)
    return fig, ax


def sentiment_bar(
    df: pd.DataFrame,
    title: str,
    save_to: Optional[Path] = None,
):
    """
    Expects a DataFrame indexed by ticker with a 'polarity' column (or
    multiple sentiment columns). Plots a bar chart.
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    cols = [c for c in df.columns if c in ("polarity", "positive_ratio", "negative_ratio")]
    if not cols:
        cols = list(df.columns)
    df[cols].plot(kind="bar", ax=ax)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Score")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=0)
    plt.tight_layout()

    if save_to:
        fig.savefig(save_to, dpi=150)
    return fig, ax

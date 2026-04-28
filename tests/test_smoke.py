"""Smoke tests — verify modules import and the lexicon scorer works."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import all_banks, find  # noqa: E402
from src.analytics.sentiment import score_sentiment  # noqa: E402


def test_universe_loads():
    banks = all_banks()
    assert len(banks) >= 5
    jpm = find("JPM")
    assert jpm.cik == "0000019617"


def test_sentiment_polarity_negative_text():
    text = "We expect adverse risks, declining revenue, and significant losses."
    s = score_sentiment(text)
    assert s.counts["negative"] > 0
    assert s.polarity < 0


def test_sentiment_polarity_positive_text():
    text = "We achieved record growth, strong gains, and improved profitability."
    s = score_sentiment(text)
    assert s.counts["positive"] > 0
    assert s.polarity > 0


if __name__ == "__main__":
    test_universe_loads()
    test_sentiment_polarity_negative_text()
    test_sentiment_polarity_positive_text()
    print("OK — smoke tests pass")

"""
Lightweight financial sentiment scoring.

This is a *lexical* baseline — it counts occurrences of words from a small
finance-specific positive/negative dictionary inspired by Loughran &
McDonald (2011). It's not a Transformer; that's deliberate:

    * No GPU / 500MB model download required.
    * Deterministic, auditable scores — important for a finance pipeline.
    * Useful as a baseline to compare a future BERT/FinBERT integration.

For real-world deployment you'd swap this for FinBERT or Claude/GPT.
The interface (`score_sentiment(text) -> dict`) is stable so the upgrade
is one-line.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

# A compact subset of L&M-style finance lexicon. Not exhaustive — it's
# intended to be representative and easy to read in a code review.
FINANCIAL_LEXICON = {
    "positive": {
        "growth", "strong", "improved", "improving", "robust", "favorable",
        "gains", "gain", "increased", "increase", "increasing", "exceeded",
        "outperformed", "record", "profitable", "profitability", "expansion",
        "opportunity", "opportunities", "successful", "achieved", "rebound",
        "resilient", "stability", "stable", "upgrade", "upgraded",
    },
    "negative": {
        "loss", "losses", "decline", "declined", "declining", "weak",
        "weakness", "deteriorated", "deteriorating", "adverse", "downturn",
        "recession", "stress", "stressed", "default", "defaults",
        "delinquency", "delinquencies", "litigation", "fraud", "breach",
        "breaches", "downgrade", "downgraded", "impairment", "impaired",
        "writedown", "write-down", "charge-off", "chargeoff", "volatile",
        "volatility", "risk", "risks", "uncertain", "uncertainty",
        "challenging", "challenges", "headwinds", "shortfall",
    },
    "uncertainty": {
        "may", "might", "could", "possibly", "uncertain", "uncertainty",
        "approximately", "estimated", "estimate", "potential", "potentially",
        "depends", "depending", "subject", "anticipate", "anticipated",
        "believe", "expect", "expected", "assume", "assumption",
    },
    "litigious": {
        "litigation", "lawsuit", "lawsuits", "settlement", "settlements",
        "plaintiff", "defendant", "judgment", "court", "regulatory",
        "investigation", "investigations", "subpoena", "indictment",
        "consent", "decree", "fine", "fines", "penalty", "penalties",
    },
}

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]+")


@dataclass
class SentimentScore:
    n_words: int
    counts: dict[str, int]      # category → raw count
    ratios: dict[str, float]    # category → count / n_words
    polarity: float             # (pos - neg) / (pos + neg + 1)

    def as_dict(self) -> dict:
        return {
            "n_words": self.n_words,
            **{f"{k}_count": v for k, v in self.counts.items()},
            **{f"{k}_ratio": round(v, 5) for k, v in self.ratios.items()},
            "polarity": round(self.polarity, 4),
        }


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def score_sentiment(text: str) -> SentimentScore:
    """
    Score a chunk of text against the finance lexicon.

    Returns counts and ratios for each category plus a single polarity
    score in [-1, 1] = (pos - neg) / (pos + neg + 1). The `+1` smooths
    the score for very short texts.
    """
    tokens = _tokenize(text)
    n = len(tokens) or 1  # avoid div-by-zero
    tok_counter = Counter(tokens)

    counts: dict[str, int] = {}
    for cat, words in FINANCIAL_LEXICON.items():
        counts[cat] = sum(tok_counter[w] for w in words)

    ratios = {cat: c / n for cat, c in counts.items()}
    pos, neg = counts["positive"], counts["negative"]
    polarity = (pos - neg) / (pos + neg + 1)

    return SentimentScore(
        n_words=n,
        counts=counts,
        ratios=ratios,
        polarity=polarity,
    )

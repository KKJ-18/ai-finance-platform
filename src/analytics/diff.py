"""
Year-over-year diff for filings.

The premise: management's narrative on risks evolves slowly. Most paragraphs
are recycled verbatim from one 10-K to the next; the *interesting* signal
sits in the *new* paragraphs and the *removed* paragraphs.

Strategy
--------
1. Split each section into paragraphs (blank-line delimited).
2. Normalise paragraphs (collapse whitespace, lowercase) for matching.
3. Treat each side as a set of normalised paragraphs:
       added   = current.paragraphs - prior.paragraphs
       removed = prior.paragraphs   - current.paragraphs
4. Surface the original (un-normalised) paragraphs back to the caller,
   plus the sentiment polarity of the diff itself.

Why paragraph-level, not sentence-level?
    Risk Factors are written in self-contained risk paragraphs (one risk =
    one paragraph). Sentence-level diff is too noisy (boilerplate sentence
    re-orderings dominate the signal). Paragraph-level cleanly isolates
    "this is a brand-new risk topic this year."

Limitations
-----------
* Paragraphs that were *edited* (not added/removed wholesale) appear as
  one removed + one added, which slightly inflates the noise. A future
  enhancement is to cluster near-duplicates with cosine similarity on
  TF-IDF vectors and treat 80%+ matches as edits, not adds.
* Order is not preserved; this is a set diff.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .sentiment import score_sentiment


@dataclass
class SectionDiff:
    ticker: str
    section: str            # "Risk Factors" or "MD&A"
    prior_date: str
    current_date: str
    n_prior: int            # paragraph counts
    n_current: int
    added: list[str]        # paragraphs new this year
    removed: list[str]      # paragraphs gone this year
    kept_count: int         # paragraphs unchanged
    prior_polarity: float
    current_polarity: float

    @property
    def churn_rate(self) -> float:
        """Share of paragraphs that changed (added + removed) / current."""
        if self.n_current == 0:
            return 0.0
        return (len(self.added) + len(self.removed)) / self.n_current

    @property
    def polarity_delta(self) -> float:
        return self.current_polarity - self.prior_polarity

    def summary(self) -> dict:
        return {
            "ticker": self.ticker,
            "section": self.section,
            "prior_date": self.prior_date,
            "current_date": self.current_date,
            "paragraphs_prior": self.n_prior,
            "paragraphs_current": self.n_current,
            "added": len(self.added),
            "removed": len(self.removed),
            "kept": self.kept_count,
            "churn_rate": round(self.churn_rate, 3),
            "prior_polarity": round(self.prior_polarity, 3),
            "current_polarity": round(self.current_polarity, 3),
            "polarity_delta": round(self.polarity_delta, 3),
        }


# -----------------------------------------------------------------------------
# Paragraph splitting and normalisation
# -----------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")
# Filter out tiny paragraphs (page numbers, bullet fragments). Real risk
# disclosure paragraphs are full sentences — at least 25 words.
MIN_WORDS = 25


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines and drop very short fragments."""
    raw = re.split(r"\n{2,}", text)
    out: list[str] = []
    for p in raw:
        p = p.strip()
        if len(p.split()) >= MIN_WORDS:
            out.append(p)
    return out


def _normalise(p: str) -> str:
    """
    Aggressive normalisation for set-membership matching.
        * lowercase
        * unify curly/straight quotes and apostrophes
        * strip all punctuation
        * collapse whitespace
    This lets paragraphs that differ only in date / minor wording / curly
    apostrophes match cleanly.
    """
    p = (
        p.lower()
        .replace("\u2019", "'")  # right single quote
        .replace("\u2018", "'")  # left single quote
        .replace("\u201c", '"')  # left double quote
        .replace("\u201d", '"')  # right double quote
        .replace("\u2013", "-")  # en dash
        .replace("\u2014", "-")  # em dash
        .replace("\xa0", " ")     # non-breaking space
    )
    p = _PUNCT_RE.sub(" ", p)
    p = _WS_RE.sub(" ", p).strip()
    return p


def _signature(p: str, n_chars: int = 80) -> str:
    """
    Fuzzy signature: first `n_chars` of the normalised paragraph.
    Two paragraphs sharing the same opening are treated as the same risk
    topic, even if the body was edited. This trades precision for recall
    in the diff and reduces noise from minor wording changes.
    """
    return _normalise(p)[:n_chars]


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def diff_sections(
    ticker: str,
    section_name: str,
    prior_text: str,
    current_text: str,
    prior_date: str,
    current_date: str,
    fuzzy: bool = True,
) -> SectionDiff:
    """
    Paragraph-level diff between two versions of a section.

    `fuzzy=True` (default) matches paragraphs by their normalised opening
    (first 80 chars), so minor wording / date edits don't show up as
    add+remove pairs. Set `fuzzy=False` for strict set-equality matching.
    """
    prior_paras = _split_paragraphs(prior_text)
    current_paras = _split_paragraphs(current_text)

    key_fn = _signature if fuzzy else _normalise
    prior_keys = {key_fn(p): p for p in prior_paras}
    current_keys = {key_fn(p): p for p in current_paras}

    added_keys = set(current_keys) - set(prior_keys)
    removed_keys = set(prior_keys) - set(current_keys)
    kept_keys = set(prior_keys) & set(current_keys)

    added = [current_keys[k] for k in added_keys]
    removed = [prior_keys[k] for k in removed_keys]

    return SectionDiff(
        ticker=ticker,
        section=section_name,
        prior_date=prior_date,
        current_date=current_date,
        n_prior=len(prior_paras),
        n_current=len(current_paras),
        added=added,
        removed=removed,
        kept_count=len(kept_keys),
        prior_polarity=score_sentiment(prior_text).polarity,
        current_polarity=score_sentiment(current_text).polarity,
    )

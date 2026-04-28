"""Analytics — correlations on returns, sentiment on filings, YoY diff."""
from .correlations import correlation_matrix, summary_stats_corr
from .sentiment import score_sentiment, FINANCIAL_LEXICON
from .diff import diff_sections, SectionDiff

__all__ = [
    "correlation_matrix",
    "summary_stats_corr",
    "score_sentiment",
    "FINANCIAL_LEXICON",
    "diff_sections",
    "SectionDiff",
]

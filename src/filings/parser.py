"""
10-K / 10-Q section extractor.

Goal: from the raw HTML filing, isolate two narrative sections that drive
most of the qualitative analysis:

    * Item 1A. Risk Factors                  (10-K)
    * Item 7.  Management's Discussion (MD&A)  (10-K)
    * Item 2.  Management's Discussion (MD&A)  (10-Q)
    * Item 1A. Risk Factors update             (10-Q, sometimes empty)

Why this is hard
----------------
Modern SEC filings (post-2020) are Inline XBRL (iXBRL): an XML envelope
wrapping XHTML, with hundreds of <ix:nonFraction> tags inline. Beyond that,
every issuer formats the prose differently:

  * Multiple tables of contents (cover, per-Part, per-Section).
  * Forwarding references ("see Item 7. Management's discussion on p. 46").
  * Body section headers that *don't* re-state "Item 7." but just
    "Management's discussion and analysis" as a standalone heading
    (this is what JPM does).
  * Curly Unicode apostrophes ('s vs 's).

Strategy
--------
1. Strip HTML/XBRL to plain text, preserving paragraph breaks.
2. Build a *two-tier* anchor list per section:
    primary  : "Item 7. Management..." style headers (works for most)
    fallback : standalone "Management's discussion and analysis" headers
              with a high signal lookahead (followed by typical body text)
3. For each candidate (start, end) pair, score by *length*. The TOC entry
   produces a tiny slice; the actual body produces tens of thousands of
   characters. Longest wins.

This is heuristic, not perfect. The unit tests cover the JPM/GS/MS/BAC/C
shape; new issuers may need their own anchor variants.
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# SEC iXBRL filings are XML-wrapped XHTML. lxml's HTML parser handles them
# fine but emits a warning we can safely suppress.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


# -----------------------------------------------------------------------------
# Section anchors we look for. Order matters — we use them to bracket sections.
#
# NOTE: 10-Q uses "Item 2." for MD&A; 10-K uses "Item 7.". We accept both
# variants and resolve which is which based on the filing's `form`.
# -----------------------------------------------------------------------------
# `\W` (any non-word) covers curly apostrophes, regular apostrophes, etc.
# `s\W*s` is permissive enough to match "Management's", "Managements",
# "Management's" (with curly apostrophe), or even an OCR-mangled variant.
MDA_BODY = r"management\W{0,2}s?\s*discussion\s*(?:and\s*analysis)?"

# Some issuers (MS, Citi) drop the "Item 1A." prefix in body headers and
# use "Risk Factors" / "RISK FACTORS" as a standalone heading.
RISK_BODY = r"risk\s*factors"

ANCHORS_10K = [
    ("item_1",    r"item\s*1\.\s*business"),
    ("item_1a",   r"item\s*1a\.\s*risk\s*factors"),
    ("risk_body", RISK_BODY),                          # Risk — fallback
    ("item_1b",   r"item\s*1b\."),
    ("item_2",    r"item\s*2\.\s*properties"),
    ("item_3",    r"item\s*3\.\s*legal\s*proceedings"),
    ("item_4",    r"item\s*4\."),
    ("item_5",    r"item\s*5\."),
    ("item_6",    r"item\s*6\."),
    ("item_7",    r"item\s*7\.\s*management"),         # MD&A — primary
    ("mda_body",  MDA_BODY),                           # MD&A — fallback
    ("item_7a",   r"item\s*7a\."),
    ("item_8",    r"item\s*8\.\s*financial\s*statements"),
    ("item_9",    r"item\s*9\."),
]

ANCHORS_10Q = [
    ("part1_item1", r"part\s*i.{0,30}item\s*1\.\s*financial"),
    ("part1_item2", r"part\s*i.{0,30}item\s*2\.\s*management"),  # MD&A
    ("part1_item3", r"part\s*i.{0,30}item\s*3\."),
    ("part1_item4", r"part\s*i.{0,30}item\s*4\."),
    ("part2_item1", r"part\s*ii.{0,30}item\s*1\.\s*legal"),
    ("part2_item1a", r"part\s*ii.{0,30}item\s*1a\.\s*risk"),     # Risk update
    ("part2_item2", r"part\s*ii.{0,30}item\s*2\."),
    ("part2_item6", r"part\s*ii.{0,30}item\s*6\."),
]


@dataclass
class FilingSections:
    """Extracted narrative sections from a 10-K or 10-Q."""

    ticker: str
    form: str
    report_date: str
    mda: str            # Management's Discussion & Analysis
    risk_factors: str   # Item 1A or Part II Item 1A

    def as_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "form": self.form,
            "report_date": self.report_date,
            "mda_chars": len(self.mda),
            "risk_factors_chars": len(self.risk_factors),
        }


# -----------------------------------------------------------------------------
# HTML → text
# -----------------------------------------------------------------------------

# Block-level tags that should be treated as paragraph boundaries when
# converting HTML to text. SEC filings use <p>, <div>, and <br>; tables
# use <tr> / <td> but we don't want a paragraph break between cells.
_BLOCK_TAGS = (
    "p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "br", "hr",
)


def html_to_text(html: str) -> str:
    """
    Convert SEC HTML/iXBRL to plain text while preserving paragraph
    structure. Each block-level tag is suffixed with a paragraph marker
    before extraction so the downstream paragraph splitter has something
    to anchor on.
    """
    soup = BeautifulSoup(html, "lxml")

    # Drop noise
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Append explicit paragraph markers AFTER block-level elements so the
    # text extractor produces "...end of paragraph.\n\n<next paragraph>"
    # instead of "...end of paragraph.\n<next>" (which would be lost in
    # whitespace collapse).
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append("\n\n")

    text = soup.get_text("\n")

    # Normalise whitespace: collapse spaces but preserve double newlines.
    text = re.sub(r"[ \t\xa0]+", " ", text)
    # Collapse 3+ newlines to exactly 2 (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove any line that is only whitespace
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    return text.strip()


# -----------------------------------------------------------------------------
# Section extraction
# -----------------------------------------------------------------------------

_HEADING_PRE_RE = re.compile(r"\n\s*\d{0,4}\s*\n\s*$")


def _is_heading_position(text: str, pos: int, lookback: int = 30) -> bool:
    """
    True if `pos` looks like the start of a heading rather than a phrase
    embedded in prose. We require the preceding `lookback` chars to end
    in "newline (optional page number) newline" — the rendering pattern
    that real section headers always exhibit in EDGAR filings, but that
    in-line cross-references do not.
    """
    pre = text[max(0, pos - lookback) : pos]
    return bool(_HEADING_PRE_RE.search(pre))


# Anchors for which we want the heading filter applied. The "Item X."
# anchors are unambiguous on their own; the MDA_BODY fallback would
# match cross-references like "see Management's discussion on p. 47"
# without this filter.
_HEADING_FILTERED_ANCHORS = {"mda_body", "risk_body"}


def _find_anchor_spans(
    text: str, anchors: list[tuple[str, str]]
) -> dict[str, list[tuple[int, int]]]:
    """
    For each anchor, return all match (start, end) positions.
    Anchors in `_HEADING_FILTERED_ANCHORS` are filtered to only positions
    that look like real section headings.
    """
    found: dict[str, list[tuple[int, int]]] = {}
    for name, pattern in anchors:
        all_spans = [
            (m.start(), m.end())
            for m in re.finditer(pattern, text, flags=re.IGNORECASE)
        ]
        if name in _HEADING_FILTERED_ANCHORS:
            all_spans = [
                (s, e) for (s, e) in all_spans if _is_heading_position(text, s)
            ]
        if all_spans:
            found[name] = all_spans
    return found


def _extract_between(
    text: str,
    start_anchors: list[tuple[int, int]],
    end_anchors: list[tuple[int, int]],
) -> str:
    """
    Given candidate start positions for the section header and candidate
    start positions for the next section, pick the (start, end) pair that
    yields the *longest* slice. This is the heuristic that filters out
    table-of-contents references (which produce tiny slices).
    """
    if not start_anchors:
        return ""

    best = ""
    for s_start, _ in start_anchors:
        # For each plausible start, find the next anchor that comes after it.
        candidate_ends = [e for e, _ in end_anchors if e > s_start]
        if candidate_ends:
            section = text[s_start : min(candidate_ends)]
        else:
            # No following anchor — take everything from s_start to end.
            section = text[s_start:]
        if len(section) > len(best):
            best = section

    return best.strip()


def extract_sections(
    html: str,
    form: str,
    ticker: str,
    report_date: str,
) -> FilingSections:
    """
    Main entry point. Given raw filing HTML and its form type, return the
    MD&A and Risk Factors sections as plain text.
    """
    text = html_to_text(html)
    form_norm = form.upper().replace(" ", "")

    if form_norm == "10-K":
        anchors = ANCHORS_10K
        spans = _find_anchor_spans(text, anchors)

        # MD&A first — its start is the upper bound for Risk Factors.
        # Pool item_7 + mda_body since JPM only labels the body as
        # "Management's discussion and analysis" without "Item 7.".
        mda_starts = spans.get("item_7", []) + spans.get("mda_body", [])
        mda_ends = spans.get("item_7a", []) + spans.get("item_8", [])
        mda = _extract_between(text, mda_starts, mda_ends)

        # Risk Factors: prefer the explicit "Item 1A." anchor when present;
        # fall back to standalone "Risk Factors" headings (MS, C).
        risk_starts = spans.get("item_1a") or spans.get("risk_body", [])
        # Ends: any of the next-section anchors PLUS the MD&A start
        # positions. Risk Factors is Item 1A; MD&A is Item 7. The Risk
        # section can never extend past the MD&A start — adding mda_starts
        # to the end candidates prevents overlap when issuers (MS, C) skip
        # the item_1b / item_2 / item_3 labels in the body.
        risk_ends = (
            spans.get("item_1b", [])
            + spans.get("item_2", [])
            + spans.get("item_3", [])
            + spans.get("item_4", [])
            + mda_starts
        )
        risk = _extract_between(text, risk_starts, risk_ends)

    elif form_norm == "10-Q":
        anchors = ANCHORS_10Q
        spans = _find_anchor_spans(text, anchors)
        # MD&A = Part I Item 2 → Part I Item 3
        mda = _extract_between(
            text,
            spans.get("part1_item2", []),
            spans.get("part1_item3", []) + spans.get("part1_item4", []),
        )
        # Risk update = Part II Item 1A → Part II Item 2
        risk = _extract_between(
            text,
            spans.get("part2_item1a", []),
            spans.get("part2_item2", []) + spans.get("part2_item6", []),
        )

    else:
        # Unsupported form — return empty payload rather than raising.
        mda, risk = "", ""

    return FilingSections(
        ticker=ticker,
        form=form,
        report_date=report_date,
        mda=mda,
        risk_factors=risk,
    )


def parse_file(
    path: Path,
    form: str,
    ticker: str,
    report_date: str,
) -> FilingSections:
    """Convenience wrapper that reads HTML from disk."""
    html = path.read_text(encoding="utf-8", errors="ignore")
    return extract_sections(html, form, ticker, report_date)

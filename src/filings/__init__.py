"""SEC EDGAR pipeline — download 10-K / 10-Q and extract MD&A + Risk Factors."""
from .edgar import EdgarClient, FilingRef
from .parser import extract_sections, FilingSections

__all__ = ["EdgarClient", "FilingRef", "extract_sections", "FilingSections"]

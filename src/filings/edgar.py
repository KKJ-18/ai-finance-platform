"""
SEC EDGAR client — minimal, dependency-light wrapper around the public
EDGAR endpoints.

Endpoints used:
    https://data.sec.gov/submissions/CIK{cik}.json
        → JSON index of every filing for a company
    https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dash_stripped}/{primary_doc}
        → the actual filing document (HTML)

SEC fair-use rules (https://www.sec.gov/os/accessing-edgar-data):
    * Provide a descriptive User-Agent identifying the requester.
    * Do not exceed 10 requests/second.

This client honours both: every request carries the configured UA, and
calls are throttled to ~5 req/s by default.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import requests

from src.config import DATA_DIR, sec_user_agent

LOG = logging.getLogger(__name__)

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVES_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{doc}"
)


@dataclass(frozen=True)
class FilingRef:
    """A single filing's metadata, enough to locate and download it."""

    cik: str               # zero-padded 10-digit
    ticker: str            # convenience
    form: str              # "10-K", "10-Q", "20-F", ...
    accession: str         # "0000019617-24-000123"
    filing_date: str       # YYYY-MM-DD
    report_date: str       # YYYY-MM-DD (period of report)
    primary_doc: str       # filename of the main HTML document

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")

    @property
    def cik_int(self) -> str:
        return str(int(self.cik))

    @property
    def url(self) -> str:
        return EDGAR_ARCHIVES_URL.format(
            cik_int=self.cik_int,
            accession_nodash=self.accession_nodash,
            doc=self.primary_doc,
        )


class EdgarClient:
    """Throttled, cached SEC EDGAR client."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        min_interval_s: float = 0.2,  # 5 req/s — well under SEC's 10 req/s cap
    ):
        self.user_agent = user_agent or sec_user_agent()
        self.cache_dir = cache_dir or (DATA_DIR / "filings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._min_interval = min_interval_s
        self._last_call_ts = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            }
        )

    # ---------------------------------------------------------------- HTTP

    def _throttle(self) -> None:
        delta = time.time() - self._last_call_ts
        if delta < self._min_interval:
            time.sleep(self._min_interval - delta)
        self._last_call_ts = time.time()

    def _get(self, url: str, host: str = "data.sec.gov") -> requests.Response:
        self._throttle()
        # The Host header changes between data.sec.gov and www.sec.gov
        headers = {"Host": host}
        LOG.debug("GET %s", url)
        r = self._session.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r

    # ------------------------------------------------------------- public

    def submissions(self, cik: str) -> dict:
        """Return the parsed submissions JSON for a CIK (zero-padded)."""
        cache = self.cache_dir / f"submissions_{cik}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))

        url = EDGAR_SUBMISSIONS_URL.format(cik=cik)
        r = self._get(url, host="data.sec.gov")
        cache.write_text(r.text, encoding="utf-8")
        return r.json()

    def _filings_pages(self, cik: str, sub: dict) -> list[dict]:
        """
        Yield every "filings" page for a CIK: the inline `recent` block,
        plus any older pages referenced under `filings.files[]`.
        Active filers (JPM, BAC...) have thousands of 8-Ks pushing 10-Ks
        out of the recent block; we must follow the older pages to find
        prior 10-Ks for YoY comparison.
        """
        pages = [sub["filings"]["recent"]]
        for f in sub["filings"].get("files", []):
            cache = self.cache_dir / f["name"]
            if cache.exists():
                pages.append(json.loads(cache.read_text(encoding="utf-8")))
                continue
            url = f"https://data.sec.gov/submissions/{f['name']}"
            r = self._get(url, host="data.sec.gov")
            cache.write_text(r.text, encoding="utf-8")
            pages.append(r.json())
        return pages

    def list_filings(
        self,
        cik: str,
        ticker: str,
        forms: Iterable[str] = ("10-K", "10-Q"),
        limit: Optional[int] = None,
    ) -> list[FilingRef]:
        """
        Return filings for a CIK matching any of `forms`, newest first.
        Walks the recent block AND older paginated files so that prior
        years' 10-Ks are reachable. `limit` caps the result count.
        """
        sub = self.submissions(cik)
        forms_set = {f.upper() for f in forms}
        out: list[FilingRef] = []

        for page in self._filings_pages(cik, sub):
            rows = zip(
                page["form"],
                page["accessionNumber"],
                page["filingDate"],
                page["reportDate"],
                page["primaryDocument"],
            )
            for form, acc, fdate, rdate, doc in rows:
                if form.upper() not in forms_set:
                    continue
                out.append(
                    FilingRef(
                        cik=cik,
                        ticker=ticker,
                        form=form,
                        accession=acc,
                        filing_date=fdate,
                        report_date=rdate,
                        primary_doc=doc,
                    )
                )
                if limit and len(out) >= limit:
                    return out
        return out

    def latest(
        self, cik: str, ticker: str, form: str = "10-K"
    ) -> Optional[FilingRef]:
        refs = self.list_filings(cik, ticker, forms=(form,), limit=1)
        return refs[0] if refs else None

    def download(self, ref: FilingRef) -> Path:
        """Download the filing's primary document. Cached on disk."""
        out = (
            self.cache_dir
            / ref.ticker
            / f"{ref.form}_{ref.report_date}_{ref.accession_nodash}.html"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.stat().st_size > 0:
            return out

        r = self._get(ref.url, host="www.sec.gov")
        out.write_bytes(r.content)
        LOG.info("Downloaded %s %s -> %s", ref.ticker, ref.form, out)
        return out

"""
Universe loader — reads config/universe.yaml and exposes helpers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "universe.yaml"
DATA_DIR = REPO_ROOT / "data"


@dataclass(frozen=True)
class Bank:
    ticker: str
    cik: Optional[str]
    name: str
    category: str

    @property
    def has_sec_filings(self) -> bool:
        return self.cik is not None


def load_universe(path: Path = CONFIG_PATH) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_banks(path: Path = CONFIG_PATH) -> list[Bank]:
    cfg = load_universe(path)
    out: list[Bank] = []
    for cat_name, cat in cfg["categories"].items():
        for m in cat["members"]:
            out.append(
                Bank(
                    ticker=m["ticker"],
                    cik=m.get("cik"),
                    name=m["name"],
                    category=cat_name,
                )
            )
    return out


def banks_by_category(category: str, path: Path = CONFIG_PATH) -> list[Bank]:
    return [b for b in all_banks(path) if b.category == category]


def find(ticker: str, path: Path = CONFIG_PATH) -> Bank:
    ticker = ticker.upper()
    for b in all_banks(path):
        if b.ticker == ticker:
            return b
    raise KeyError(f"Ticker {ticker} not found in universe.yaml")


def sec_user_agent(path: Path = CONFIG_PATH) -> str:
    """SEC EDGAR requires a descriptive User-Agent. Env var wins over YAML."""
    env = os.environ.get("SEC_USER_AGENT")
    if env:
        return env
    cfg = load_universe(path)
    ua = cfg.get("sec_user_agent")
    if not ua:
        raise RuntimeError(
            "No SEC User-Agent configured. Set SEC_USER_AGENT env var or "
            "edit config/universe.yaml."
        )
    return ua

"""Deduplicate Yahoo Finance screener listings into one organization per issuer."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from naas_abi_marketplace.applications.yahoofinance.integrations.YahooFinanceScreenerIntegration import (
    local_screener_root,
)

DEFAULT_INPUT = local_screener_root() / "_all" / "all_screener.json"
DEFAULT_OUTPUT = local_screener_root() / "_all" / "all_screener_dedup.json"

ORG_FIELDS = ("companyName", "sector", "industry")
LEGAL_SUFFIX_RE = re.compile(
    r"""
    (?:
        societe\ anonyme |
        s\.?\s*a\.? |
        incorporated |
        corporation |
        company |
        limited |
        corp\.? |
        inc\.? |
        ltd\.? |
        llc\.? |
        plc\.? |
        n\.?v\.? |
        a\.?g\.? |
        s\.?p\.?a\.? |
        gmbh |
        b\.?v\.? |
        pty\.? |
        pte\.? |
        tbk\.? |
        co\.?
    )
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)
LEADING_ENTITY_RE = re.compile(r"^(?:pt|the)\s+", re.IGNORECASE)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def fold_text(value: str) -> str:
    """ASCII-fold and lowercase a company name."""
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def organization_key(company_name: str | None, ticker: str | None) -> str:
    """Return a stable grouping key for one issuer."""
    if not company_name or not company_name.strip():
        return f"ticker:{(ticker or '').strip().upper()}"

    key = fold_text(company_name.strip())
    key = LEADING_ENTITY_RE.sub("", key)
    changed = True
    while changed:
        stripped = LEGAL_SUFFIX_RE.sub("", key).strip(" .,/")
        changed = stripped != key
        key = stripped
    key = NON_ALNUM_RE.sub(" ", key).strip()
    return key or f"ticker:{(ticker or '').strip().upper()}"


def _numeric(record: dict[str, Any], field: str) -> float:
    value = record.get(field)
    if isinstance(value, dict):
        raw = value.get("raw")
        if isinstance(raw, (int, float)):
            return float(raw)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def listing_rank(record: dict[str, Any]) -> tuple[float, float, str]:
    """Prefer the most traded listing, then the largest market cap."""
    return (
        _numeric(record, "avgDailyVol3m"),
        _numeric(record, "marketCap"),
        str(record.get("ticker") or ""),
    )


def listing_parameters(record: dict[str, Any]) -> dict[str, Any]:
    """Keep listing-specific fields, including the stock id."""
    parameters = {
        key: value for key, value in record.items() if key not in ORG_FIELDS
    }
    parameters["stockId"] = record.get("ticker")
    return parameters


def canonical_name(listings: list[dict[str, Any]]) -> str | None:
    names = [record.get("companyName") for record in listings if record.get("companyName")]
    if not names:
        return None
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    primary = max(listings, key=listing_rank)
    return max(counts, key=lambda name: (counts[name], name == primary.get("companyName"), name))


def build_organization(listings: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse one issuer's listings into an organization with listing parameters."""
    ordered = sorted(listings, key=listing_rank, reverse=True)
    primary = ordered[0]
    return {
        "companyName": canonical_name(ordered),
        "sector": primary.get("sector"),
        "industry": primary.get("industry"),
        "primaryTicker": primary.get("ticker"),
        "listingCount": len(ordered),
        "parameters": {
            "stockIds": [record.get("ticker") for record in ordered],
            "listings": [listing_parameters(record) for record in ordered],
        },
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pages = payload.get("finance", {}).get("result") or []
    if not pages:
        return []
    records = pages[0].get("records") or []
    if not isinstance(records, list):
        raise ValueError(f"{path} does not contain a records list")
    return records


def dedup_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = organization_key(record.get("companyName"), record.get("ticker"))
        grouped[key].append(record)
    organizations = [build_organization(listings) for listings in grouped.values()]
    organizations.sort(
        key=lambda org: (
            (org.get("companyName") or "").lower(),
            org.get("primaryTicker") or "",
        )
    )
    return organizations

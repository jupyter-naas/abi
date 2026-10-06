"""Resolve Nexus Sheets seed templates for create-from-chat."""

from __future__ import annotations

import re

DEFAULT_SHEETS_TEMPLATE_ID = "grid-light-v1"

_KNOWN_STEMS = frozenset(
    {
        "grid-light-v1",
        "monthly-pnl-v1",
        "budget-vs-actuals-v1",
        "cash-runway-v1",
    }
)

# Order matters: more specific finance intents first.
_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(budget\s*vs\.?\s*actuals?|budget\s+versus|variance\s+analysis|"
            r"actuals?\s+vs\.?\s+budget)\b",
            re.IGNORECASE,
        ),
        "budget-vs-actuals-v1",
    ),
    (
        re.compile(
            r"\b(cash\s+runway|runway\s+months?|burn\s+rate|cash\s+rollforward|"
            r"cash\s+forecast)\b",
            re.IGNORECASE,
        ),
        "cash-runway-v1",
    ),
    (
        re.compile(
            r"\b(p\s*&\s*l|p\s+and\s+l|pnl|profit\s+and\s+loss|income\s+statement|"
            r"monthly\s+p\s*&\s*l)\b",
            re.IGNORECASE,
        ),
        "monthly-pnl-v1",
    ),
)


def normalize_sheets_template_id(template_id: str | None) -> str:
    raw = (template_id or "").strip()
    if not raw:
        return DEFAULT_SHEETS_TEMPLATE_ID
    stem = raw.split("/", 1)[-1].strip().lower()
    if stem in _KNOWN_STEMS:
        return stem
    return DEFAULT_SHEETS_TEMPLATE_ID


def resolve_sheets_template_id(
    *,
    template_id: str = "",
    title: str = "",
    brief: str = "",
) -> str:
    """Pick a catalog stem: explicit id, else finance hint from title/brief, else blank."""
    explicit = (template_id or "").strip()
    if explicit:
        stem = normalize_sheets_template_id(explicit)
        if stem != DEFAULT_SHEETS_TEMPLATE_ID or explicit.split("/")[-1] in {
            DEFAULT_SHEETS_TEMPLATE_ID,
            "blank",
        }:
            if explicit.split("/")[-1].lower() in _KNOWN_STEMS or stem in _KNOWN_STEMS:
                return normalize_sheets_template_id(explicit)
    haystack = f"{title}\n{brief}"
    for pattern, stem in _HINTS:
        if pattern.search(haystack):
            return stem
    return DEFAULT_SHEETS_TEMPLATE_ID


def qualify_sheets_template_id(stem: str) -> str:
    return f"abi/{normalize_sheets_template_id(stem)}"

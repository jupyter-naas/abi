"""Leaf utilities shared by the X graph-builder modules.

Kept dependency-free (no imports from sibling builder modules) so the
per-entity ``build_*`` files and :mod:`_graph_builder` can all import from
here without creating an import cycle.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional


def uri_for(namespace: str, class_name: str, stable_id: str) -> str:
    """Deterministic IRI under *namespace* for *class_name* keyed on *stable_id*."""
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", stable_id)
    return f"{namespace}{class_name}/{safe}"


def parse_dt(value: Any) -> Optional[datetime]:
    """Parse an X v2 ISO-8601 timestamp, tolerating the trailing ``Z`` form."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def first(value: Any) -> Optional[str]:
    """Return the first item of a list, the string itself, or None."""
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None

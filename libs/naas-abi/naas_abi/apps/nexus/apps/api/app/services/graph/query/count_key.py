"""Stable cache key for the per-spec COUNT (AUDIT §7b.6).

The count is invariant to ordering and pagination, so the key hashes the spec **minus
sort**, namespaced by workspace + the graph union, so two workspaces (or two graph sets)
with structurally identical specs never collide. A ``_SEMVER`` prefix lets a compiler
change logically retire old entries (they keep their old key; the TTL reaps them).

v1 keeps the filter-tree child order (a reordered-but-equivalent filter is a cache miss,
not a wrong answer). Per-graph generation tokens for eager invalidation are a follow-up;
today the 10-min TTL + the existing ``_invalidate_graph_cache`` hooks bound staleness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

_SEMVER = "v1"


def _normalize(spec: Any) -> dict:
    """The count-relevant projection of a spec: everything except ``sort``."""
    data = asdict(spec)  # recurses nested frozen dataclasses; tuples → lists
    data.pop("sort", None)  # COUNT is sort-invariant
    return data


def count_cache_key(spec: Any, *, workspace_id: str) -> str:
    payload = {
        "semver": _SEMVER,
        "workspace": workspace_id,
        "spec": _normalize(spec),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "view_count_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def page_cache_key(spec: Any, *, workspace_id: str, page: Any) -> str:
    """Stable cache key for a page of ROWS.

    Unlike the count, rows depend on ordering AND pagination, so the key hashes the FULL spec
    (sort included) plus the page window (limit / offset / keyset cursor), namespaced by
    workspace. Same ``_SEMVER`` reaping behaviour as the count key.
    """
    payload = {
        "semver": _SEMVER,
        "workspace": workspace_id,
        "spec": asdict(spec),
        "page": asdict(page),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "view_page_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

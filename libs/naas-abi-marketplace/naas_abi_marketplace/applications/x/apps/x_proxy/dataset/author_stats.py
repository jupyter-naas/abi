"""Cached per-author aggregates (recomputed when new posts are ingested)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.canonical import (
    canonical_cte,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.matched_tweets import (
    matched_index_ready,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHOR_STATS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
    upsert_table,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _author_id_filter(author_ids: list[str]) -> str:
    ids = [_escape(aid.strip()) for aid in author_ids if str(aid or "").strip()]
    if not ids:
        return ""
    quoted = ", ".join(f"'{aid}'" for aid in ids)
    return f" AND author_id IN ({quoted})"


def aggregate_author_stats(
    dataset,
    author_ids: list[str],
) -> list[dict[str, Any]]:
    """Canonical post totals for the given authors (live SQL)."""
    ids = [str(aid or "").strip() for aid in author_ids if str(aid or "").strip()]
    if not ids:
        return []
    ensure_x_datasets(dataset)
    cte = canonical_cte(use_matched_index=matched_index_ready(dataset))
    id_filter = _author_id_filter(ids)
    result = dataset.query(
        f"WITH {cte} "
        f"SELECT author_id, "
        f"SUM(CASE WHEN kind = 'matched' THEN 1 ELSE 0 END) AS matched_count, "
        f"SUM(CASE WHEN kind = 'referenced' THEN 1 ELSE 0 END) AS referenced_count, "
        f"MIN(created_at) AS first_post_at, "
        f"MAX(created_at) AS last_post_at "
        f"FROM canonical_enriched "
        f"WHERE author_id <> ''{id_filter} "
        f"GROUP BY author_id",
        namespace=X_DATASET_NAMESPACE,
    )
    return list(result.rows)


def recompute_author_stats(dataset, author_ids: list[str]) -> int:
    """Refresh ``author_stats_v1`` rows for authors touched by a sync batch."""
    rows = aggregate_author_stats(dataset, author_ids)
    if not rows:
        return 0
    now = _utc_now()
    payload: list[dict[str, Any]] = []
    for row in rows:
        author_id = str(row.get("author_id") or "").strip()
        if not author_id:
            continue
        payload.append(
            {
                "author_id": author_id,
                "matched_count": int(row.get("matched_count") or 0),
                "referenced_count": int(row.get("referenced_count") or 0),
                "first_post_at": row.get("first_post_at") or now,
                "last_post_at": row.get("last_post_at") or now,
                "updated_at": now,
            }
        )
    return upsert_table(dataset, AUTHOR_STATS_V1, payload)


def earliest_post_at_by_author(dataset) -> dict[str, Any]:
    """First retrieved tweet per author: sort posts by ``created_at``, one row each.

    Same as pandas ``sort_values('created_at').drop_duplicates('author_id')``.
    """
    ensure_x_datasets(dataset)
    cte = canonical_cte(use_matched_index=matched_index_ready(dataset))
    result = dataset.query(
        f"WITH {cte} "
        f"SELECT author_id, MIN(created_at) AS first_post_at "
        f"FROM canonical_enriched "
        f"WHERE author_id <> '' "
        f"GROUP BY author_id",
        namespace=X_DATASET_NAMESPACE,
    )
    out: dict[str, Any] = {}
    for row in result.rows:
        author_id = str(row.get("author_id") or "").strip()
        if author_id and row.get("first_post_at") is not None:
            out[author_id] = row["first_post_at"]
    return out


def stamp_missing_first_post_at_from_posts(dataset) -> int:
    """Write ``first_post_at`` onto stats rows that still have it null.

    New authors get the field on first ingest via ``recompute_author_stats``.
    Everyone already in ``author_stats_v1`` is filled from the posts table.
    """
    ensure_x_datasets(dataset)
    missing = dataset.query(
        f"SELECT * FROM {AUTHOR_STATS_V1} "
        f"WHERE author_id <> '' AND first_post_at IS NULL",
        namespace=X_DATASET_NAMESPACE,
    )
    if not missing.rows:
        return 0
    earliest = earliest_post_at_by_author(dataset)
    if not earliest:
        return 0
    now = _utc_now()
    payload: list[dict[str, Any]] = []
    for row in missing.rows:
        author_id = str(row.get("author_id") or "").strip()
        first_post_at = earliest.get(author_id)
        if not author_id or first_post_at is None:
            continue
        payload.append(
            {
                "author_id": author_id,
                "matched_count": int(row.get("matched_count") or 0),
                "referenced_count": int(row.get("referenced_count") or 0),
                "first_post_at": first_post_at,
                "last_post_at": row.get("last_post_at") or first_post_at,
                "updated_at": now,
            }
        )
    if not payload:
        return 0
    return upsert_table(dataset, AUTHOR_STATS_V1, payload)


def count_authors_missing_first_post(dataset) -> int:
    """How many ``author_stats_v1`` rows still have a null first post."""
    ensure_x_datasets(dataset)
    result = dataset.query(
        f"SELECT COUNT(*) AS n FROM {AUTHOR_STATS_V1} "
        f"WHERE author_id <> '' AND first_post_at IS NULL",
        namespace=X_DATASET_NAMESPACE,
    )
    if not result.rows:
        return 0
    return int(result.rows[0]["n"] or 0)


def fetch_author_stats(dataset, author_id: str) -> dict[str, Any] | None:
    """Read cached stats for one author."""
    aid = str(author_id or "").strip()
    if not aid:
        return None
    ensure_x_datasets(dataset)
    escaped = _escape(aid)
    result = dataset.query(
        f"SELECT * FROM {AUTHOR_STATS_V1} WHERE author_id = '{escaped}' LIMIT 1",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    if not result.rows:
        return None
    return dict(result.rows[0])


def _stats_complete(stats: dict[str, Any] | None) -> bool:
    """True when the cache row can serve the user-page KPIs without a recompute."""
    return stats is not None and stats.get("first_post_at") is not None


def profile_stats(dataset, author_id: str) -> dict[str, Any] | None:
    """Cached stats, recomputing when missing or ``first_post_at`` is null.

    Rows created before ``first_post_at`` was added still have counts and
    ``last_post_at``; treating those as complete left First post retrieved empty.
    """
    stats = fetch_author_stats(dataset, author_id)
    if _stats_complete(stats):
        return stats
    recompute_author_stats(dataset, [author_id])
    return fetch_author_stats(dataset, author_id)


def merge_profile_with_stats(
    author: dict[str, Any], stats: dict[str, Any] | None
) -> dict[str, Any]:
    """Shape an author row for the user feed / KPI JSON."""
    profile = dict(author)
    if not stats:
        return profile
    matched = int(stats.get("matched_count") or 0)
    referenced = int(stats.get("referenced_count") or 0)
    profile["matched_count"] = matched
    profile["referenced_count"] = referenced
    profile["posts"] = matched + referenced
    profile["last_post_at"] = stats.get("last_post_at")
    profile["first_post_at"] = stats.get("first_post_at")
    return profile

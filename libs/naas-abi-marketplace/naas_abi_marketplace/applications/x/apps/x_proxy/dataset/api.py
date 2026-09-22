"""Read helpers for dataset-backed X Proxy HTTP endpoints."""

from __future__ import annotations

import re
from typing import Any

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.author_stats import (
    merge_profile_with_stats,
    profile_stats,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.canonical import (
    canonical_cte,
    canonical_posts_cte,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.matched_tweets import (
    matched_index_ready,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHOR_STATS_V1,
    AUTHORS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)

_RESULT_TOTAL_COLUMN = "_result_total"

_HANDLE = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _tweet_needle_filter(needle: str) -> str:
    n = _escape(needle.strip().lower().lstrip("@"))
    if not n:
        return ""
    return (
        f" WHERE lower(full_text) LIKE '%{n}%' "
        f"OR lower(text) LIKE '%{n}%' "
        f"OR lower(username) LIKE '%{n}%' "
        f"OR lower(location) LIKE '%{n}%' "
        f"OR lower(tweet_id) LIKE '%{n}%'"
    )


def _user_needle_filter(needle: str) -> str:
    n = _escape(needle.strip().lower().lstrip("@"))
    if not n:
        return ""
    return (
        f" WHERE lower(username) LIKE '%{n}%' "
        f"OR lower(display_name) LIKE '%{n}%' "
        f"OR lower(description) LIKE '%{n}%' "
        f"OR lower(location) LIKE '%{n}%'"
    )


def graph_totals(dataset) -> dict[str, int]:
    """Distinct ingested tweets (matched + referenced), same as ``globals/graph.json``."""
    ensure_x_datasets(dataset)
    cte = canonical_cte(use_matched_index=matched_index_ready(dataset))
    result = dataset.query(
        f"WITH {cte} "
        f"SELECT COUNT(*) AS posts, "
        f"SUM(CASE WHEN kind = 'matched' THEN 1 ELSE 0 END) AS matched "
        f"FROM canonical_enriched",
        namespace=X_DATASET_NAMESPACE,
    )
    row = result.rows[0] if result.rows else {}
    posts = int(row.get("posts") or 0)
    matched = int(row.get("matched") or 0)
    return {
        "posts": posts,
        "matched": matched,
        "referenced": max(0, posts - matched),
    }


def search_users(
    dataset,
    query: str,
    *,
    offset: int = 0,
    limit: int = 100,
) -> tuple[int, list[dict[str, Any]]]:
    """Authors with at least one canonical ingested post."""
    ensure_x_datasets(dataset)
    cte = canonical_cte(use_matched_index=matched_index_ready(dataset))
    where = _user_needle_filter(query)
    if where:
        where = where.replace(" WHERE ", " AND ", 1)
    count = dataset.query(
        f"WITH {cte}, authors_with_posts AS ("
        f"  SELECT author_id, COUNT(*) AS post_rows, "
        f"  MIN(created_at) AS first_post_at, MAX(created_at) AS last_post_at "
        f"  FROM canonical_enriched GROUP BY author_id"
        f") "
        f"SELECT COUNT(*) AS n FROM {AUTHORS_V1} a "
        f"INNER JOIN authors_with_posts awp ON a.author_id = awp.author_id "
        f"WHERE 1=1{where}",
        namespace=X_DATASET_NAMESPACE,
    )
    total = int(count.rows[0]["n"]) if count.rows else 0
    result = dataset.query(
        f"WITH {cte}, authors_with_posts AS ("
        f"  SELECT author_id, "
        f"  SUM(CASE WHEN kind = 'matched' THEN 1 ELSE 0 END) AS matched_count, "
        f"  SUM(CASE WHEN kind = 'referenced' THEN 1 ELSE 0 END) AS referenced_count, "
        f"  MIN(created_at) AS first_post_at, "
        f"  MAX(created_at) AS last_post_at "
        f"  FROM canonical_enriched GROUP BY author_id"
        f") "
        f"SELECT a.*, awp.matched_count, awp.referenced_count, "
        f"awp.first_post_at, awp.last_post_at "
        f"FROM {AUTHORS_V1} a "
        f"INNER JOIN authors_with_posts awp ON a.author_id = awp.author_id "
        f"WHERE 1=1{where} "
        f"ORDER BY awp.matched_count + awp.referenced_count DESC, a.username "
        f"LIMIT {int(limit)} OFFSET {int(offset)}",
        namespace=X_DATASET_NAMESPACE,
    )
    return total, list(result.rows)


def _total_from_stats(
    stats: dict[str, Any] | None,
    kind: str | None,
) -> int | None:
    if not stats:
        return None
    matched = int(stats.get("matched_count") or 0)
    referenced = int(stats.get("referenced_count") or 0)
    if kind == "matched":
        return matched
    if kind == "referenced":
        return referenced
    return matched + referenced


def _stats_from_joined_author(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("stat_matched_count") is None and row.get("stat_referenced_count") is None:
        return None
    stats: dict[str, Any] = {
        "matched_count": int(row.get("stat_matched_count") or 0),
        "referenced_count": int(row.get("stat_referenced_count") or 0),
        "last_post_at": row.get("stat_last_post_at"),
    }
    if row.get("stat_first_post_at") is not None:
        stats["first_post_at"] = row.get("stat_first_post_at")
    return stats


def _clean_author_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if not key.startswith("stat_")
    }


def _posts_with_profile_fields(
    rows: list[dict[str, Any]],
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    username = str(profile.get("username") or "")
    location = str(profile.get("location") or "")
    verified_type = str(profile.get("verified_type") or "")
    display_name = str(profile.get("display_name") or "")
    description = str(profile.get("description") or "")
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.setdefault("username", username)
        item.setdefault("location", location)
        item.setdefault("verified_type", verified_type)
        item.setdefault("display_name", display_name)
        item.setdefault("description", description)
        out.append(item)
    return out


def _post_rows_without_internal(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.pop(_RESULT_TOTAL_COLUMN, None)
        cleaned.append(item)
    return cleaned


def user_posts(
    dataset,
    username: str,
    *,
    offset: int = 0,
    limit: int = 100,
    kind: str | None = None,
) -> tuple[dict[str, Any] | None, int, list[dict[str, Any]]]:
    ensure_x_datasets(dataset)
    handle = username.strip().lstrip("@")
    if not _HANDLE.fullmatch(handle):
        return None, 0, []
    escaped = _escape(handle.lower())
    author = dataset.query(
        f"SELECT a.*, "
        f"s.matched_count AS stat_matched_count, "
        f"s.referenced_count AS stat_referenced_count, "
        f"s.first_post_at AS stat_first_post_at, "
        f"s.last_post_at AS stat_last_post_at "
        f"FROM {AUTHORS_V1} a "
        f"LEFT JOIN {AUTHOR_STATS_V1} s ON a.author_id = s.author_id "
        f"WHERE lower(a.username) = '{escaped}' LIMIT 1",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    if not author.rows:
        return None, 0, []
    joined = dict(author.rows[0])
    author_row = _clean_author_row(joined)
    author_id_raw = str(author_row.get("author_id") or "")
    stats = _stats_from_joined_author(joined)
    if stats is None:
        stats = profile_stats(dataset, author_id_raw)
    profile = merge_profile_with_stats(author_row, stats)
    cte = canonical_posts_cte(
        author_id=author_id_raw,
        use_matched_index=matched_index_ready(dataset),
    )
    kind_filter = ""
    if kind in ("matched", "referenced"):
        kind_filter = f" AND kind = '{kind}'"
    cached_total = _total_from_stats(stats, kind)
    posts = dataset.query(
        f"WITH {cte}, filtered AS ("
        f"  SELECT p.*, COUNT(*) OVER () AS {_RESULT_TOTAL_COLUMN} "
        f"  FROM canonical_posts p "
        f"  WHERE 1=1{kind_filter}"
        f") "
        f"SELECT * FROM filtered "
        f"ORDER BY created_at DESC "
        f"LIMIT {int(limit)} OFFSET {int(offset)}",
        namespace=X_DATASET_NAMESPACE,
    )
    rows = list(posts.rows)
    if rows:
        total = int(rows[0].get(_RESULT_TOTAL_COLUMN) or 0)
    elif cached_total is not None:
        total = cached_total
    else:
        total = 0
    cleaned = _post_rows_without_internal(rows)
    return profile, total, _posts_with_profile_fields(cleaned, profile)


def serialize_search_posts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shape dataset rows for the Search Tweets JSON API."""
    out: list[dict[str, Any]] = []
    for row in rows:
        media = str(row.get("media_urls") or "").split()
        out.append(
            {
                "tweet_id": str(row.get("tweet_id") or ""),
                "created_at": str(row.get("created_at") or ""),
                "text": str(row.get("full_text") or row.get("text") or ""),
                "username": str(row.get("username") or ""),
                "location": str(row.get("location") or ""),
                "verified_type": str(row.get("verified_type") or ""),
                "referenced": row.get("kind") == "referenced",
                "media_count": len(media),
                "queries": [str(row.get("query_slug") or "")] if row.get("query_slug") else [],
            }
        )
    return out


def search_tweets(
    dataset,
    query: str,
    *,
    offset: int = 0,
    limit: int = 100,
) -> tuple[int, list[dict[str, Any]]]:
    ensure_x_datasets(dataset)
    cte = canonical_cte(use_matched_index=matched_index_ready(dataset))
    where = _tweet_needle_filter(query)
    count = dataset.query(
        f"WITH {cte} SELECT COUNT(*) AS n FROM canonical_enriched{where}",
        namespace=X_DATASET_NAMESPACE,
    )
    total = int(count.rows[0]["n"]) if count.rows else 0
    result = dataset.query(
        f"WITH {cte} SELECT * FROM canonical_enriched{where} "
        f"ORDER BY created_at DESC "
        f"LIMIT {int(limit)} OFFSET {int(offset)}",
        namespace=X_DATASET_NAMESPACE,
    )
    return total, list(result.rows)


def post_by_id(dataset, tweet_id: str) -> dict[str, Any] | None:
    ensure_x_datasets(dataset)
    if not tweet_id.isdigit():
        return None
    escaped = _escape(tweet_id)
    cte = canonical_cte(use_matched_index=matched_index_ready(dataset))
    result = dataset.query(
        f"WITH {cte} SELECT * FROM canonical_enriched "
        f"WHERE tweet_id = '{escaped}' LIMIT 1",
        namespace=X_DATASET_NAMESPACE,
    )
    return dict(result.rows[0]) if result.rows else None

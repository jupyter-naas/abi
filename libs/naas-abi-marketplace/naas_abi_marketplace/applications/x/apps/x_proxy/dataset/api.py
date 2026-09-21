"""Read helpers for dataset-backed X Proxy HTTP endpoints."""

from __future__ import annotations

import re
from typing import Any

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.canonical import (
    canonical_cte,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHORS_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)

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
        f"OR lower(description) LIKE '%{n}%'"
    )


def graph_totals(dataset) -> dict[str, int]:
    """Distinct ingested tweets (matched + referenced), same as ``globals/graph.json``."""
    ensure_x_datasets(dataset)
    cte = canonical_cte()
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
    cte = canonical_cte()
    where = _user_needle_filter(query)
    if where:
        where = where.replace(" WHERE ", " AND ", 1)
    count = dataset.query(
        f"WITH {cte}, authors_with_posts AS ("
        f"  SELECT author_id, COUNT(*) AS post_rows, MAX(created_at) AS last_post_at "
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
        f"  MAX(created_at) AS last_post_at "
        f"  FROM canonical_enriched GROUP BY author_id"
        f") "
        f"SELECT a.*, awp.matched_count, awp.referenced_count, awp.last_post_at "
        f"FROM {AUTHORS_V1} a "
        f"INNER JOIN authors_with_posts awp ON a.author_id = awp.author_id "
        f"WHERE 1=1{where} "
        f"ORDER BY awp.matched_count + awp.referenced_count DESC, a.username "
        f"LIMIT {int(limit)} OFFSET {int(offset)}",
        namespace=X_DATASET_NAMESPACE,
    )
    return total, list(result.rows)


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
        f"SELECT * FROM {AUTHORS_V1} WHERE lower(username) = '{escaped}' LIMIT 1",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    if not author.rows:
        return None, 0, []
    profile = dict(author.rows[0])
    author_id = _escape(str(profile.get("author_id") or ""))
    cte = canonical_cte()
    kind_filter = ""
    if kind in ("matched", "referenced"):
        kind_filter = f" AND kind = '{kind}'"
    count = dataset.query(
        f"WITH {cte} "
        f"SELECT COUNT(*) AS n FROM canonical_posts "
        f"WHERE author_id = '{author_id}'{kind_filter}",
        namespace=X_DATASET_NAMESPACE,
    )
    total = int(count.rows[0]["n"]) if count.rows else 0
    posts = dataset.query(
        f"WITH {cte} "
        f"SELECT * FROM canonical_posts "
        f"WHERE author_id = '{author_id}'{kind_filter} "
        f"ORDER BY created_at DESC LIMIT {int(limit)} OFFSET {int(offset)}",
        namespace=X_DATASET_NAMESPACE,
    )
    return profile, total, list(posts.rows)


def search_tweets(
    dataset,
    query: str,
    *,
    offset: int = 0,
    limit: int = 100,
) -> tuple[int, list[dict[str, Any]]]:
    ensure_x_datasets(dataset)
    cte = canonical_cte()
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
    cte = canonical_cte()
    result = dataset.query(
        f"WITH {cte} SELECT * FROM canonical_enriched "
        f"WHERE tweet_id = '{escaped}' LIMIT 1",
        namespace=X_DATASET_NAMESPACE,
    )
    return dict(result.rows[0]) if result.rows else None

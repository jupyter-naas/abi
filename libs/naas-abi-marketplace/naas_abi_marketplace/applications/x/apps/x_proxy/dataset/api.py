"""Read helpers for dataset-backed X Proxy HTTP endpoints.

Every endpoint answers in two steps: first the *keys* of what it returns
(narrow columns, filtered before any ranking), then the full rows for that one
page, fetched by key. Joining every post to every author, or ranking every
post's text, is what made a search cost seconds on a million-row table.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Iterable
from typing import Any

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.author_stats import (
    merge_profile_with_stats,
    profile_stats,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.canonical import (
    CANONICAL_KEY_COLUMNS,
    CANONICAL_RANK_SQL,
    VALID_TWEET_ID_SQL,
    canonical_cte,
    canonical_keys_sql,
    matched_ids_query,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.matched_tweets import (
    matched_index_ready,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHOR_STATS_V1,
    AUTHORS_V1,
    MATCHED_TWEET_IDS_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)

_RESULT_TOTAL_COLUMN = "_result_total"
_USER_RN_COLUMN = "_user_rn"

_HANDLE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

# Post columns the endpoints publish, and the author fields merged onto them
# (the ``canonical_enriched`` shape).
_POST_COLUMNS = (
    "tweet_id",
    "kind",
    "query_slug",
    "created_at",
    "author_id",
    "text",
    "full_text",
    "lang",
    "media_urls",
)
_POST_AUTHOR_COLUMNS = (
    "username",
    "location",
    "verified_type",
    "display_name",
    "description",
)
_STATS_COLUMNS = ("matched_count", "referenced_count", "first_post_at", "last_post_at")

# ``author_stats_v1`` only ever fills up, so once it has rows it stays usable.
_author_stats_ready: weakref.WeakSet[Any] = weakref.WeakSet()


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _sql_in(values: Iterable[str]) -> str:
    return ", ".join(f"'{_escape(str(value))}'" for value in values)


def _user_needle_and_clause(needle: str, *, alias: str = "a") -> str:
    n = _escape(needle.strip().lower().lstrip("@"))
    if not n:
        return ""
    return (
        f" AND (lower({alias}.username) LIKE '%{n}%' "
        f"OR lower({alias}.display_name) LIKE '%{n}%' "
        f"OR lower({alias}.description) LIKE '%{n}%' "
        f"OR lower({alias}.location) LIKE '%{n}%')"
    )


def _tweet_needle_scan_clause(needle: str) -> str:
    """Needle over ``posts_v1`` columns; author fields go through ``author_id``.

    Same fields as before (text, handle, location, tweet id), but the handle and
    location are resolved to author ids once instead of joining every post to
    its author before filtering.
    """
    n = _escape(needle.strip().lower().lstrip("@"))
    if not n:
        return ""
    return (
        f" AND (lower(full_text) LIKE '%{n}%' "
        f"OR lower(text) LIKE '%{n}%' "
        f"OR tweet_id LIKE '%{n}%' "
        f"OR author_id IN (SELECT author_id FROM {AUTHORS_V1} "
        f"WHERE lower(username) LIKE '%{n}%' OR lower(location) LIKE '%{n}%'))"
    )


def graph_totals(dataset) -> dict[str, int]:
    """Distinct ingested tweets (matched + referenced), same as ``globals/graph.json``.

    Every distinct tweet id is exactly one canonical row, and the matched index
    holds exactly the ids that ever matched - so both totals are plain counts,
    with no per-tweet ranking.
    """
    ensure_x_datasets(dataset)
    if matched_index_ready(dataset):
        matched_sql = (
            f"SELECT count(*) FROM {MATCHED_TWEET_IDS_V1} WHERE {VALID_TWEET_ID_SQL}"
        )
    else:
        matched_sql = (
            f"SELECT count(DISTINCT tweet_id) FROM {POSTS_V1} "
            f"WHERE {VALID_TWEET_ID_SQL} AND kind = 'matched'"
        )
    result = dataset.query(
        f"SELECT (SELECT count(DISTINCT tweet_id) FROM {POSTS_V1} "
        f"WHERE {VALID_TWEET_ID_SQL}) AS posts, "
        f"({matched_sql}) AS matched",  # nosec B608
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


def _author_stats_search_ready(dataset) -> bool:
    """True when sync has populated ``author_stats_v1`` (maintained on ingest)."""
    if dataset in _author_stats_ready:
        return True
    ensure_x_datasets(dataset)
    probe = dataset.query(
        f"SELECT 1 AS ok FROM {AUTHOR_STATS_V1} LIMIT 1",
        namespace=X_DATASET_NAMESPACE,
    )
    if probe.rows:
        _author_stats_ready.add(dataset)
        return True
    return False


def _search_total_from_rows(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(rows[0].get(_RESULT_TOTAL_COLUMN) or 0)


def _paged_keys(
    dataset,
    keys_sql: str,
    *,
    order_by: str,
    offset: int,
    limit: int,
) -> tuple[int, list[dict[str, Any]]]:
    """One page of ``keys_sql`` plus its total, in one scan of the keys."""
    result = dataset.query(
        f"WITH keys AS MATERIALIZED ({keys_sql}) "
        f"SELECT page.*, (SELECT count(*) FROM keys) AS {_RESULT_TOTAL_COLUMN} "
        f"FROM (SELECT * FROM keys ORDER BY {order_by} "
        f"LIMIT {int(limit)} OFFSET {int(offset)}) page "
        f"ORDER BY {order_by}",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    rows = list(result.rows)
    if rows or offset <= 0:
        return _search_total_from_rows(rows), rows
    # Paged past the end: the page is empty but the total is still owed.
    count = dataset.query(
        f"SELECT count(*) AS n FROM ({keys_sql}) keys",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    return int(count.rows[0]["n"]) if count.rows else 0, []


def _username_dedupe_rank_order(*, prefix: str = "j") -> str:
    """Pick one ``author_id`` per handle; matches ``user_posts`` resolution."""
    p = prefix
    return (
        f"{p}.seen_at DESC NULLS LAST, "
        f"{p}.matched_count + {p}.referenced_count DESC, "
        f"{p}.author_id"
    )


def _deduped_users_select_cte(*, joined_sql: str) -> str:
    """One row per ``lower(username)``; stats from the chosen ``author_id`` only."""
    rank = _username_dedupe_rank_order(prefix="j")
    return f"""
joined AS (
{joined_sql}
),
deduped AS (
  SELECT * EXCLUDE ({_USER_RN_COLUMN})
  FROM (
    SELECT
      j.*,
      ROW_NUMBER() OVER (
        PARTITION BY lower(j.username)
        ORDER BY {rank}
      ) AS {_USER_RN_COLUMN}
    FROM joined j
    WHERE length(j.username) > 0
  ) ranked
  WHERE {_USER_RN_COLUMN} = 1
)
"""


def _authors_with_stats(dataset, author_ids: list[str]) -> list[dict[str, Any]]:
    """``authors_v1`` rows + their ``author_stats_v1`` counts, for a few ids."""
    if not author_ids:
        return []
    ids = _sql_in(author_ids)
    stats = ", ".join(f"s.{column}" for column in _STATS_COLUMNS)
    result = dataset.query(
        f"SELECT a.*, {stats} "
        f"FROM (SELECT * FROM {AUTHORS_V1} WHERE author_id IN ({ids})) a "
        f"INNER JOIN (SELECT * FROM {AUTHOR_STATS_V1} WHERE author_id IN ({ids})) s "
        f"ON a.author_id = s.author_id",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    return list(result.rows)


def _search_users_via_stats(
    dataset,
    query: str,
    *,
    offset: int,
    limit: int,
) -> tuple[int, list[dict[str, Any]]]:
    # ``authors_v1`` is upserted on ``author_id``, so it already holds one row
    # per author; only the handle needs deduping (one X account can reappear
    # under a new id).
    and_clause = _user_needle_and_clause(query)
    total_posts = "s.matched_count + s.referenced_count"
    keys_sql = (
        f"SELECT a.author_id, a.username, {total_posts} AS _posts "
        f"FROM {AUTHORS_V1} a "
        f"INNER JOIN {AUTHOR_STATS_V1} s ON a.author_id = s.author_id "
        f"WHERE a.author_id <> '' AND length(a.username) > 0{and_clause} "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY lower(a.username) "
        f"ORDER BY a.seen_at DESC NULLS LAST, {total_posts} DESC, a.author_id) = 1"
    )
    total, keys = _paged_keys(
        dataset,
        keys_sql,
        order_by="_posts DESC, username",
        offset=offset,
        limit=limit,
    )
    order = [str(key["author_id"]) for key in keys]
    by_id = {
        str(row["author_id"]): row for row in _authors_with_stats(dataset, order)
    }
    return total, [dict(by_id[aid]) for aid in order if aid in by_id]


def _search_users_via_canonical(
    dataset,
    query: str,
    *,
    offset: int,
    limit: int,
) -> tuple[int, list[dict[str, Any]]]:
    cte = canonical_cte(use_matched_index=matched_index_ready(dataset))
    and_clause = _user_needle_and_clause(query)
    joined = (
        f"  SELECT a.*, awp.matched_count, awp.referenced_count, "
        f"  awp.first_post_at, awp.last_post_at "
        f"  FROM authors_deduped a "
        f"  INNER JOIN authors_with_posts awp ON a.author_id = awp.author_id "
        f"  WHERE 1=1{and_clause}"
    )
    dedupe = _deduped_users_select_cte(joined_sql=joined)
    result = dataset.query(
        f"WITH {cte}, authors_with_posts AS ("
        f"  SELECT author_id, "
        f"  SUM(CASE WHEN kind = 'matched' THEN 1 ELSE 0 END) AS matched_count, "
        f"  SUM(CASE WHEN kind = 'referenced' THEN 1 ELSE 0 END) AS referenced_count, "
        f"  MIN(created_at) AS first_post_at, "
        f"  MAX(created_at) AS last_post_at "
        f"  FROM canonical_enriched GROUP BY author_id"
        f"), {dedupe}, filtered AS ("
        f"  SELECT *, COUNT(*) OVER () AS {_RESULT_TOTAL_COLUMN} "
        f"  FROM deduped"
        f") "
        f"SELECT * FROM filtered "
        f"ORDER BY matched_count + referenced_count DESC, username "
        f"LIMIT {int(limit)} OFFSET {int(offset)}",
        namespace=X_DATASET_NAMESPACE,
    )
    rows = list(result.rows)
    return _search_total_from_rows(rows), _post_rows_without_internal(rows)


def search_users(
    dataset,
    query: str,
    *,
    offset: int = 0,
    limit: int = 100,
) -> tuple[int, list[dict[str, Any]]]:
    """Authors with at least one canonical ingested post."""
    ensure_x_datasets(dataset)
    if _author_stats_search_ready(dataset):
        return _search_users_via_stats(
            dataset, query, offset=int(offset), limit=int(limit)
        )
    return _search_users_via_canonical(
        dataset, query, offset=int(offset), limit=int(limit)
    )


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


def _resolve_author(dataset, handle: str) -> dict[str, Any] | None:
    """Newest ``author_id`` behind a handle, with its cached stats columns."""
    escaped = _escape(handle.lower())
    candidates = dataset.query(
        f"SELECT * FROM {AUTHORS_V1} "
        f"WHERE author_id <> '' AND lower(username) = '{escaped}'",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    if not candidates.rows:
        return None
    ids = [str(row["author_id"]) for row in candidates.rows]
    stats_rows = dataset.query(
        f"SELECT * FROM {AUTHOR_STATS_V1} WHERE author_id IN ({_sql_in(ids)})",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    stats_by_id = {str(row["author_id"]): row for row in stats_rows.rows}
    joined: list[dict[str, Any]] = []
    for row in candidates.rows:
        item = dict(row)
        stats = stats_by_id.get(str(row["author_id"])) or {}
        for column in _STATS_COLUMNS:
            item[f"stat_{column}"] = stats.get(column)
        joined.append(item)

    # Same order as the handle dedupe in ``search_users``: newest ``seen_at``
    # (missing last), then the busier id, then ``author_id`` - as stable sorts,
    # least significant first.
    joined.sort(key=lambda row: str(row["author_id"]))
    joined.sort(
        key=lambda row: int(row.get("stat_matched_count") or 0)
        + int(row.get("stat_referenced_count") or 0),
        reverse=True,
    )
    joined.sort(key=lambda row: str(row.get("seen_at") or ""), reverse=True)
    return joined[0]


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
    joined = _resolve_author(dataset, handle)
    if joined is None:
        return None, 0, []
    author_row = _clean_author_row(joined)
    author_id_raw = str(author_row.get("author_id") or "")
    stats = _stats_from_joined_author(joined)
    if stats is None:
        stats = profile_stats(dataset, author_id_raw)
    profile = merge_profile_with_stats(author_row, stats)
    # Kind is filtered after ranking: a referenced row loses to its matched twin.
    kind_filter = ""
    if kind in ("matched", "referenced"):
        kind_filter = f" WHERE kind = '{kind}'"
    columns = ", ".join(_POST_COLUMNS)
    matched_ids = matched_ids_query(use_index=matched_index_ready(dataset))
    posts = dataset.query(
        f"WITH canonical_posts AS MATERIALIZED ("
        f"  SELECT {columns} FROM {POSTS_V1} "
        f"  WHERE {VALID_TWEET_ID_SQL} AND author_id = '{_escape(author_id_raw)}' "
        f"  AND (kind = 'matched' OR tweet_id NOT IN ({matched_ids})) "
        f"  QUALIFY {CANONICAL_RANK_SQL} = 1"
        f"), filtered AS ("
        f"  SELECT * FROM canonical_posts{kind_filter}"
        f") "
        f"SELECT *, (SELECT count(*) FROM filtered) AS {_RESULT_TOTAL_COLUMN} "
        f"FROM filtered "
        f"ORDER BY created_at DESC NULLS LAST, tweet_id DESC "
        f"LIMIT {int(limit)} OFFSET {int(offset)}",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    rows = list(posts.rows)
    cached_total = _total_from_stats(stats, kind)
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


def _enriched_posts(dataset, keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Full ``canonical_enriched`` rows for a page of canonical keys, in order."""
    if not keys:
        return []
    tweet_ids = _sql_in(sorted({str(key["tweet_id"]) for key in keys}))
    author_ids = sorted({str(key.get("author_id") or "") for key in keys} - {""})
    post_columns = ", ".join(f"p.{column}" for column in _POST_COLUMNS)
    author_columns = ", ".join(
        f"COALESCE(a.{column}, '') AS {column}" for column in _POST_AUTHOR_COLUMNS
    )
    authors = (
        f"(SELECT * FROM {AUTHORS_V1} WHERE author_id IN ({_sql_in(author_ids)}))"
        if author_ids
        else f"(SELECT * FROM {AUTHORS_V1} WHERE false)"
    )
    result = dataset.query(
        f"SELECT {post_columns}, {author_columns} "
        f"FROM (SELECT * FROM {POSTS_V1} WHERE tweet_id IN ({tweet_ids})) p "
        f"LEFT JOIN {authors} a ON p.author_id = a.author_id",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    by_key = {
        (str(row["tweet_id"]), row.get("kind"), row.get("query_slug")): row
        for row in result.rows
    }
    out: list[dict[str, Any]] = []
    for key in keys:
        row = by_key.get((str(key["tweet_id"]), key.get("kind"), key.get("query_slug")))
        if row is not None:
            out.append(dict(row))
    return out


def search_tweets(
    dataset,
    query: str,
    *,
    offset: int = 0,
    limit: int = 100,
) -> tuple[int, list[dict[str, Any]]]:
    ensure_x_datasets(dataset)
    keys_sql = canonical_keys_sql(
        where=_tweet_needle_scan_clause(query),
        use_matched_index=matched_index_ready(dataset),
    )
    total, keys = _paged_keys(
        dataset,
        keys_sql,
        order_by="created_at DESC NULLS LAST, tweet_id DESC",
        offset=int(offset),
        limit=int(limit),
    )
    return total, _enriched_posts(dataset, keys)


def post_by_id(dataset, tweet_id: str) -> dict[str, Any] | None:
    ensure_x_datasets(dataset)
    if not tweet_id.isdigit():
        return None
    # Every row of one tweet is in ``posts_v1``, so ranking those few rows is
    # the whole canonical rule - no need to rank the table.
    keys = dataset.query(
        f"SELECT {CANONICAL_KEY_COLUMNS} FROM {POSTS_V1} "
        f"WHERE tweet_id = '{_escape(tweet_id)}' "
        f"ORDER BY CASE WHEN kind = 'matched' THEN 0 ELSE 1 END, "
        f"created_at DESC NULLS LAST LIMIT 1",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    rows = _enriched_posts(dataset, list(keys.rows))
    return rows[0] if rows else None

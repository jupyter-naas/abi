"""Dataset-backed reader for X app snapshot publish (parity with ``CacheReader``)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.matched_tweets import (
    matched_index_ready,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHORS_V1,
    COUNT_BUCKETS_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)

KIND_MATCHED = "matched"
KIND_REFERENCED = "referenced"

_FACET_COLUMNS = frozenset({"username", "location", "verified_type"})


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _matched_ids_subquery(*, use_index: bool) -> str:
    if use_index:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
            MATCHED_TWEET_IDS_V1,
        )

        return f"SELECT tweet_id FROM {MATCHED_TWEET_IDS_V1} WHERE tweet_id <> ''"
    return (
        f"SELECT DISTINCT tweet_id FROM {POSTS_V1} "
        f"WHERE kind = 'matched' AND tweet_id <> ''"
    )


def _scoped_posts_cte(*, query_slug: str, use_index: bool) -> str:
    slug = _escape(query_slug)
    matched_ids = _matched_ids_subquery(use_index=use_index)
    return f"""
scoped_posts AS (
  SELECT p.*
  FROM {POSTS_V1} p
  WHERE p.query_slug = '{slug}'
    AND p.tweet_id <> ''
    AND regexp_full_match(p.tweet_id, '^[0-9]+$')
    AND (
      p.kind = 'matched'
      OR p.tweet_id NOT IN ({matched_ids})
    )
)
"""


class DatasetSnapshotReader:
    """SQL queries over DuckLake tables for snapshot publish."""

    def __init__(self, dataset: IDatasetPort) -> None:
        self._dataset = dataset
        ensure_x_datasets(dataset)
        self._use_index = matched_index_ready(dataset)

    def _query(self, sql: str) -> list[dict[str, Any]]:
        result = self._dataset.query(sql, namespace=X_DATASET_NAMESPACE)
        return list(result.rows)

    def release_window_cache(self) -> int:
        return 0

    def known_query_slugs(self) -> set[str]:
        rows = self._query(
            f"SELECT DISTINCT query_slug AS slug FROM {POSTS_V1} "
            f"WHERE query_slug <> ''"
        )
        return {str(r["slug"]) for r in rows if r.get("slug")}

    def earliest_matched_created_at(self) -> datetime | None:
        rows = self._query(
            f"SELECT MIN(created_at) AS mn FROM {POSTS_V1} WHERE kind = 'matched'"
        )
        if not rows:
            return None
        return _parse_ts(rows[0].get("mn"))

    def count_endpoint_timeseries(self, query_slug: str) -> list[dict[str, Any]]:
        """Hourly count-endpoint buckets for one slug (complete hours only)."""
        slug = _escape(query_slug)
        rows = self._query(
            f"SELECT bucket_start, bucket_end, tweet_count "
            f"FROM {COUNT_BUCKETS_V1} "
            f"WHERE query_slug = '{slug}' "
            f"AND bucket_end NOT LIKE '%-partial' "
            f"ORDER BY bucket_start"
        )
        buckets: list[dict[str, Any]] = []
        for row in rows:
            start = row.get("bucket_start")
            if not start:
                continue
            end = row.get("bucket_end")
            count = row.get("tweet_count")
            buckets.append(
                {
                    "start": str(start),
                    "end": str(end) if end is not None else None,
                    "count": int(count) if count is not None else 0,
                }
            )
        return buckets

    def count_in_window(
        self,
        start_time: str,
        end_time: str,
        *,
        referenced: bool = False,
        query_slug: str | None = None,
    ) -> int:
        if query_slug is None:
            return 0
        kind = KIND_REFERENCED if referenced else KIND_MATCHED
        start = _escape(start_time)
        end = _escape(end_time)
        cte = _scoped_posts_cte(query_slug=query_slug, use_index=self._use_index)
        rows = self._query(
            f"WITH {cte} "
            f"SELECT COUNT(*) AS n FROM scoped_posts "
            f"WHERE kind = '{kind}' "
            f"AND created_at >= TIMESTAMP '{start}' "
            f"AND created_at < TIMESTAMP '{end}'"
        )
        return int(rows[0]["n"]) if rows else 0

    def hourly_counts(
        self,
        start_time: str,
        end_time: str,
        *,
        query_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        if query_slug is None:
            return []
        start = _escape(start_time)
        end = _escape(end_time)
        cte = _scoped_posts_cte(query_slug=query_slug, use_index=self._use_index)
        rows = self._query(
            f"WITH {cte} "
            f"SELECT date_trunc('hour', created_at) AS hour, "
            f"COUNT(DISTINCT tweet_id) AS cnt "
            f"FROM scoped_posts "
            f"WHERE kind = 'matched' "
            f"AND created_at >= TIMESTAMP '{start}' "
            f"AND created_at < TIMESTAMP '{end}' "
            f"GROUP BY 1 ORDER BY 1"
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            hour = _parse_ts(row.get("hour"))
            if hour is None:
                continue
            nxt = hour + timedelta(hours=1)
            out.append(
                {
                    "start": hour.isoformat(),
                    "end": nxt.isoformat(),
                    "count": int(row.get("cnt") or 0),
                }
            )
        return out

    def facet_values(
        self,
        start_time: str,
        end_time: str,
        column: str,
        *,
        limit: int = 500,
        query_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        if query_slug is None or column not in _FACET_COLUMNS:
            return []
        start = _escape(start_time)
        end = _escape(end_time)
        cte = _scoped_posts_cte(query_slug=query_slug, use_index=self._use_index)
        col = _escape(column)
        lim = max(1, int(limit))
        rows = self._query(
            f"WITH {cte}, "
            f"authors_deduped AS ("
            f"  SELECT author_id, username, location, verified_type "
            f"  FROM ("
            f"    SELECT *, ROW_NUMBER() OVER ("
            f"      PARTITION BY author_id ORDER BY seen_at DESC NULLS LAST"
            f"    ) AS _rn FROM {AUTHORS_V1} WHERE author_id <> ''"
            f"  ) t WHERE _rn = 1"
            f"), "
            f"enriched AS ("
            f"  SELECT sp.tweet_id, "
            f"  COALESCE(a.username, '') AS username, "
            f"  COALESCE(a.location, '') AS location, "
            f"  COALESCE(a.verified_type, '') AS verified_type "
            f"  FROM scoped_posts sp "
            f"  LEFT JOIN authors_deduped a ON sp.author_id = a.author_id "
            f"  WHERE sp.kind = 'matched' "
            f"  AND sp.created_at >= TIMESTAMP '{start}' "
            f"  AND sp.created_at < TIMESTAMP '{end}'"
            f") "
            f"SELECT trim({col}) AS value, COUNT(DISTINCT tweet_id) AS cnt "
            f"FROM enriched "
            f"GROUP BY 1 "
            f"ORDER BY cnt DESC, value "
            f"LIMIT {lim}"
        )
        return [
            {"value": str(r.get("value") or ""), "count": int(r.get("cnt") or 0)}
            for r in rows
        ]

    def newest_posts(
        self,
        start_time: str,
        end_time: str,
        *,
        limit: int = 1000,
        query_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        if query_slug is None:
            return []
        start = _escape(start_time)
        end = _escape(end_time)
        cte = _scoped_posts_cte(query_slug=query_slug, use_index=self._use_index)
        lim = max(1, int(limit))
        rows = self._query(
            f"WITH {cte}, "
            f"authors_deduped AS ("
            f"  SELECT author_id, username, location, verified_type "
            f"  FROM ("
            f"    SELECT *, ROW_NUMBER() OVER ("
            f"      PARTITION BY author_id ORDER BY seen_at DESC NULLS LAST"
            f"    ) AS _rn FROM {AUTHORS_V1} WHERE author_id <> ''"
            f"  ) t WHERE _rn = 1"
            f") "
            f"SELECT sp.created_at, sp.text, sp.full_text, sp.tweet_id, "
            f"COALESCE(a.username, '') AS username, "
            f"COALESCE(a.location, '') AS location, "
            f"COALESCE(a.verified_type, '') AS verified_type "
            f"FROM scoped_posts sp "
            f"LEFT JOIN authors_deduped a ON sp.author_id = a.author_id "
            f"WHERE sp.kind = 'matched' "
            f"AND sp.created_at >= TIMESTAMP '{start}' "
            f"AND sp.created_at < TIMESTAMP '{end}' "
            f"ORDER BY sp.created_at DESC "
            f"LIMIT {lim}"
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            username = str(row.get("username") or "")
            tweet_id = str(row.get("tweet_id") or "")
            created = _parse_ts(row.get("created_at"))
            if created is None:
                continue
            full = str(row.get("full_text") or "")
            text = str(row.get("text") or "")
            out.append(
                {
                    "created_at": created.isoformat(),
                    "text": full or text,
                    "url": (
                        f"https://x.com/{username}/status/{tweet_id}"
                        if username and tweet_id
                        else ""
                    ),
                    "username": username,
                    "location": str(row.get("location") or ""),
                    "verified_type": str(row.get("verified_type") or ""),
                }
            )
        return out

"""Canonical tweet projection for dataset reads (parity with ``CacheReader.posts()``).

The Parquet reader drops referenced rows when the same ``tweet_id`` ever appears
as matched anywhere, then collapses to one row per tweet for search. Dataset
SQL reads apply the same rules so totals match a full envelope backfill.
"""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHORS_V1,
    POSTS_V1,
)

# One row per tweet: matched typing wins, then newest ``created_at``.
CANONICAL_POSTS_CTE = """
canonical_posts AS (
  WITH matched_ids AS (
    SELECT DISTINCT tweet_id FROM {posts}
    WHERE kind = 'matched' AND tweet_id <> ''
  ),
  filtered AS (
    SELECT p.*
    FROM {posts} p
    WHERE p.tweet_id <> ''
      AND regexp_full_match(p.tweet_id, '^[0-9]+$')
      AND (
        p.kind = 'matched'
        OR p.tweet_id NOT IN (SELECT tweet_id FROM matched_ids)
      )
  ),
  ranked AS (
    SELECT
      f.*,
      ROW_NUMBER() OVER (
        PARTITION BY f.tweet_id
        ORDER BY
          CASE WHEN f.kind = 'matched' THEN 0 ELSE 1 END,
          f.created_at DESC NULLS LAST
      ) AS _rn
    FROM filtered f
  )
  SELECT * FROM ranked WHERE _rn = 1
)
"""

CANONICAL_WITH_AUTHORS_CTE = (
    CANONICAL_POSTS_CTE
    + """,
canonical_enriched AS (
  SELECT
    p.tweet_id,
    p.kind,
    p.query_slug,
    p.created_at,
    p.author_id,
    p.text,
    p.full_text,
    p.lang,
    p.media_urls,
    COALESCE(a.username, '') AS username,
    COALESCE(a.location, '') AS location,
    COALESCE(a.verified_type, '') AS verified_type,
    COALESCE(a.display_name, '') AS display_name,
    COALESCE(a.description, '') AS description
  FROM canonical_posts p
  LEFT JOIN {authors} a ON p.author_id = a.author_id
)
"""
)


def canonical_cte(*, posts: str = POSTS_V1, authors: str = AUTHORS_V1) -> str:
    return CANONICAL_WITH_AUTHORS_CTE.format(posts=posts, authors=authors)

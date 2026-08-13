"""Layout and schemas of the X columnar read model.

The triple store stays the source of truth. This is a *projection*: a columnar
copy of the same ingest envelopes, shaped for the aggregate-heavy questions the
dashboard asks (counts per window, top values per column, newest N posts, totals
per author). Those are exactly the questions SPARQL answers by scanning the whole
graph, which is why the publish cost grew with total history rather than with the
window being displayed.

On-disk layout, under the object storage root::

    x/cache/
    ├── posts/ym=YYYY-MM/part-<stamp>.parquet
    ├── authors.parquet
    └── manifest.json

Partitioned by **month**, not day: referenced tweets are conversation parents and
quoted originals that can be years older than the ingest that pulled them in, so
a per-day layout scatters a long sparse tail across thousands of near-empty files.
By month a 30-day window still touches only two partitions.

Each part file is written sorted by ``created_at`` with statistics enabled, so a
window filter skips whole row groups without decompressing them.
"""

from __future__ import annotations

from typing import Any

CACHE_PREFIX = "x/cache"
POSTS_DIR = f"{CACHE_PREFIX}/posts"
AUTHORS_KEY = "authors.parquet"
MANIFEST_KEY = "manifest.json"

# Where the ingest writes its envelopes — the log this projection reads.
ENVELOPE_PREFIX = "x/search_recent_tweets"

# Redis key holding the newest envelope timestamp already projected. Kept in the
# kv service rather than the manifest so an incremental run can decide whether
# there is anything to do without fetching the manifest.
WATERMARK_KEY = "x:cache:watermark"

# Bumped when the on-disk column set changes in a way a reader cannot tolerate.
# A manifest recording a different version forces a full rebuild.
SCHEMA_VERSION = 1

# A post is one row per (tweet_id, kind). ``kind`` separates the posts that
# answered the query from the ones the expansions pulled in as context — the
# dashboard reports them separately and must never conflate them.
KIND_MATCHED = "matched"
KIND_REFERENCED = "referenced"


def post_schema() -> dict[str, Any]:
    import polars as pl

    return {
        "tweet_id": pl.Utf8,
        "kind": pl.Utf8,
        "query_slug": pl.Utf8,
        "created_at": pl.Datetime(time_unit="us", time_zone="UTC"),
        "author_id": pl.Utf8,
        "text": pl.Utf8,
        "lang": pl.Utf8,
        "conversation_id": pl.Utf8,
        "like_count": pl.Int32,
        "retweet_count": pl.Int32,
        "reply_count": pl.Int32,
        "media_urls": pl.Utf8,
    }


def author_schema() -> dict[str, Any]:
    import polars as pl

    return {
        "author_id": pl.Utf8,
        "username": pl.Utf8,
        "display_name": pl.Utf8,
        "description": pl.Utf8,
        "location": pl.Utf8,
        "verified_type": pl.Utf8,
        "verified": pl.Boolean,
        "protected": pl.Boolean,
        "is_identity_verified": pl.Boolean,
        "user_url": pl.Utf8,
        "profile_image_url": pl.Utf8,
        "profile_banner_url": pl.Utf8,
        "user_created_at": pl.Utf8,
        "most_recent_tweet_id": pl.Utf8,
        "followers_count": pl.Int64,
        "following_count": pl.Int64,
        "tweet_count": pl.Int64,
        "listed_count": pl.Int64,
        "user_like_count": pl.Int64,
        "media_count": pl.Int64,
        # When this profile was last observed in an envelope — the tie-breaker
        # that decides which of several observations of one author wins.
        "seen_at": pl.Utf8,
    }


def partition_key(month: str) -> str:
    """Object-storage prefix holding one month of posts."""
    return f"{POSTS_DIR}/ym={month}"

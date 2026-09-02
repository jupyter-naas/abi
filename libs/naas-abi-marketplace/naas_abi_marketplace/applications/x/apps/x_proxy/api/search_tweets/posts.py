"""Publish the Search Tweets dataset: every post in the tweet graph.

The web app reads this straight from object storage - no SPARQL at request time::

    search_tweets/
    ├── posts_preview.json   # newest 1 000 posts - fast first paint
    └── posts.json           # every post - loaded when a search is submitted

The Search Tweets page is not scoped by scenario or query. It must search the
whole graph, not the newest 1 000 rows per window that ``tables.json`` carries
for the Search Recent Tweets table.

Built from the Parquet projection when one exists (a column scan over resident
rows); otherwise one uncapped SPARQL read. Re-publishing is skipped when the
projection watermark has not moved since the last publish.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_TWEET_LIMIT,
    SnapshotContext,
    content_digest,
    encode_compact,
)

# Column order of the compact rows in ``posts.json``. Arrays, not objects: at
# ~110k posts the object form more than doubles the file the search page loads.
INDEX_COLUMNS = [
    "tweet_id",
    "created_at",
    "text",
    "username",
    "location",
    "verified_type",
    "referenced",
    "media_count",
    "queries",
]

DATASET_FORMAT = 1


def _index_row(post: dict[str, Any]) -> list[Any]:
    queries = post.get("queries") or []
    return [
        post.get("tweet_id") or "",
        post.get("created_at") or "",
        post.get("text") or "",
        post.get("username") or "",
        post.get("location") or "",
        post.get("verified_type") or "",
        1 if post.get("referenced") else 0,
        int(post.get("media_count") or 0),
        " ".join(queries),
    ]


def _read_posts(ctx: SnapshotContext) -> list[dict[str, Any]]:
    cache = getattr(ctx, "cache", None)
    if cache is not None:
        return cache.tweet_search_index()
    return ctx.all_tweets_for_search()


def publish(ctx: SnapshotContext) -> dict:
    """Write the Search Tweets dataset and return a summary."""
    previous_doc = ctx.read_json("search_tweets", "manifest.json") or {}
    cache = getattr(ctx, "cache", None)
    source_state = (
        cache.projection_state() if cache is not None else ctx.tweet_graph_state()
    )
    if (
        previous_doc.get("format") == DATASET_FORMAT
        and source_state
        and previous_doc.get("source_state") == source_state
        and previous_doc.get("index_columns") == INDEX_COLUMNS
    ):
        logger.info(
            f"X app tweets dataset: source unchanged ({source_state}) - "
            "kept the published dataset"
        )
        return {
            "skipped": True,
            "posts": int(previous_doc.get("count") or 0),
            "preview": int(previous_doc.get("preview") or 0),
        }

    posts = _read_posts(ctx)
    preview_limit = DEFAULT_TWEET_LIMIT
    preview = posts[:preview_limit]

    index_body = {
        "format": DATASET_FORMAT,
        "count": len(posts),
        "preview": len(preview),
        "columns": INDEX_COLUMNS,
        "posts": [_index_row(p) for p in posts],
    }
    index_hash = content_digest(encode_compact(index_body))
    preview_body = {
        "format": DATASET_FORMAT,
        "count": len(posts),
        "preview": len(preview),
        "columns": INDEX_COLUMNS,
        "posts": [_index_row(p) for p in preview],
    }
    preview_hash = content_digest(encode_compact(preview_body))

    index_written = previous_doc.get("index_hash") != index_hash
    preview_written = previous_doc.get("preview_hash") != preview_hash

    if index_written:
        ctx.save_bytes(
            "search_tweets",
            "posts.json",
            encode_compact({"updated_at": ctx.built_at.isoformat(), **index_body}),
        )
    if preview_written:
        ctx.save_bytes(
            "search_tweets",
            "posts_preview.json",
            encode_compact({"updated_at": ctx.built_at.isoformat(), **preview_body}),
        )

    manifest = {
        "updated_at": ctx.built_at.isoformat(),
        "format": DATASET_FORMAT,
        "count": len(posts),
        "preview": len(preview),
        "source_state": source_state,
        "index_hash": index_hash,
        "preview_hash": preview_hash,
        "index_columns": INDEX_COLUMNS,
    }
    ctx.save_json_compact("search_tweets", "manifest.json", manifest)

    summary = {
        "posts": len(posts),
        "preview": len(preview),
        "index_written": index_written,
        "preview_written": preview_written,
    }
    logger.info(f"X app tweets dataset: {summary}")
    return summary

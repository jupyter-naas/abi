"""Turn one ingest envelope into post and author rows.

Pure functions over the envelope dict — no services, no I/O — so the mapping that
has to stay faithful to :class:`XSearchRecentTweetsPipeline` is directly testable.

An envelope is what ``XSearchRecentTweetsWorkflow`` persisted for a single tick::

    {query, options, results: {data, includes, errors, meta, sources},
     started_at, ended_at, file_path, batch}

``results.data`` are the posts that answered the query; ``results.includes.tweets``
is a *superset* of it — X hydrates every id referenced by a match, and a post that
both matched and is referenced by another match appears in both arrays.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from naas_abi_marketplace.applications.x.cache.schema import (
    KIND_MATCHED,
    KIND_REFERENCED,
)

# Envelope object keys start with the tick's ISO timestamp, but the archive holds
# two spellings: early files replaced every ``:`` with ``_``
# (``2026-06-29T17_58_45.974146+00_00_…``), later ones kept it
# (``2026-08-12T05:55:16.152505+00:00_…``). Both must parse, or the watermark
# silently skips whichever era it cannot read.
_TIMESTAMP = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}[:_]\d{2}[:_]\d{2}(?:\.\d+)?"
    r"(?:[+-]\d{2}[:_]\d{2}|Z)?)"
)


def envelope_timestamp(key: str) -> datetime | None:
    """The tick time encoded in an envelope's object key, or ``None``.

    Used as the projection watermark, so it must never guess: an unparseable key
    is reported as ``None`` and the caller processes the envelope rather than
    skipping it.
    """
    name = key.rsplit("/", 1)[-1]
    match = _TIMESTAMP.search(name)
    if not match:
        return None
    raw = match.group(1)
    # Restore the separators the filesystem-safe spelling replaced. Only the time
    # and offset are touched; the date's hyphens are already valid.
    date_part, _, time_part = raw.partition("T")
    time_part = time_part.replace("_", ":")
    try:
        return datetime.fromisoformat(f"{date_part}T{time_part}")
    except ValueError:
        return None


def slugify(value: str) -> str:
    """Match ``apps.x.api.common.slugify`` so slugs line up with the snapshots."""
    keep = [c if c.isalnum() else "_" for c in value.lower()]
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:80] or "query"


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _media_by_key(includes: dict) -> dict[str, str]:
    """``media_key -> best available URL`` for the envelope's attached media.

    Videos and animated GIFs carry no ``url``; falling back to the still keeps a
    thumbnail rather than dropping the attachment entirely.
    """
    out: dict[str, str] = {}
    for media in includes.get("media") or []:
        key = media.get("media_key")
        if key:
            out[key] = media.get("url") or media.get("preview_image_url") or ""
    return out


def _post_row(
    record: dict, kind: str, query_slug: str, media_by_key: dict[str, str]
) -> dict[str, Any] | None:
    created = _parse_dt(record.get("created_at"))
    if created is None or not record.get("id"):
        return None
    metrics = record.get("public_metrics") or {}
    media_keys = (record.get("attachments") or {}).get("media_keys") or []
    media = " ".join(u for u in (media_by_key.get(k) for k in media_keys) if u)
    return {
        "tweet_id": str(record["id"]),
        "kind": kind,
        "query_slug": query_slug,
        "created_at": created,
        "author_id": str(record.get("author_id") or ""),
        "text": record.get("text") or "",
        "lang": record.get("lang") or "",
        "conversation_id": str(record.get("conversation_id") or ""),
        "like_count": int(metrics.get("like_count") or 0),
        "retweet_count": int(metrics.get("retweet_count") or 0),
        "reply_count": int(metrics.get("reply_count") or 0),
        "media_urls": media,
    }


def _author_row(record: dict, seen_at: str) -> dict[str, Any] | None:
    if not record.get("id"):
        return None
    metrics = record.get("public_metrics") or {}
    return {
        "author_id": str(record["id"]),
        "username": record.get("username") or "",
        "display_name": record.get("name") or "",
        "description": record.get("description") or "",
        # X omits `location` entirely unless the profile sets one.
        "location": record.get("location") or "",
        "verified_type": record.get("verified_type") or "",
        "verified": bool(record.get("verified")),
        "protected": bool(record.get("protected")),
        "is_identity_verified": bool(record.get("is_identity_verified")),
        "user_url": record.get("url") or "",
        "profile_image_url": record.get("profile_image_url") or "",
        "profile_banner_url": record.get("profile_banner_url") or "",
        "user_created_at": record.get("created_at") or "",
        "most_recent_tweet_id": str(record.get("most_recent_tweet_id") or ""),
        "followers_count": int(metrics.get("followers_count") or 0),
        "following_count": int(metrics.get("following_count") or 0),
        "tweet_count": int(metrics.get("tweet_count") or 0),
        "listed_count": int(metrics.get("listed_count") or 0),
        "user_like_count": int(metrics.get("like_count") or 0),
        "media_count": int(metrics.get("media_count") or 0),
        "seen_at": seen_at,
    }


def parse_envelope(doc: dict) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(post rows, author rows)`` for one envelope.

    Mirrors ``XSearchRecentTweetsPipeline._map``: a post present in ``data`` is a
    match, and anything in ``includes.tweets`` sharing an id with it is the *same*
    post rather than context, so it is not emitted again as referenced. Skipping
    this in a first draft inflated the referenced population about 25x, because
    in a single-topic stream most context posts also matched at some point.
    """
    results = doc.get("results") or {}
    if not isinstance(results, dict):
        return [], []
    query_slug = slugify(str(doc.get("query") or ""))
    seen_at = str(doc.get("ended_at") or doc.get("started_at") or "")
    includes = results.get("includes") or {}
    media_by_key = _media_by_key(includes)

    data = results.get("data") or []
    matched_ids = {str(r["id"]) for r in data if r.get("id")}

    posts: list[dict[str, Any]] = []
    for record in data:
        row = _post_row(record, KIND_MATCHED, query_slug, media_by_key)
        if row:
            posts.append(row)
    for record in includes.get("tweets") or []:
        if str(record.get("id") or "") in matched_ids:
            continue
        row = _post_row(record, KIND_REFERENCED, query_slug, media_by_key)
        if row:
            posts.append(row)

    authors: list[dict[str, Any]] = []
    for record in includes.get("users") or []:
        row = _author_row(record, seen_at)
        if row:
            authors.append(row)
    return posts, authors

"""Incremental envelope → Dataset Service projection."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.envelopes import (
    parse_envelope,
    slugify,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.schema import (
    ENVELOPE_PREFIX,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.storage import split_key
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.author_stats import (
    recompute_author_stats,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.matched_tweets import (
    upsert_matched_tweet_ids_from_posts,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHORS_V1,
    COUNT_BUCKETS_V1,
    ENVELOPES_V1,
    MEDIA_V1,
    POST_MEDIA_V1,
    POSTS_V1,
    PROJECTION_COMMITS_V1,
    envelope_already_ingested,
    upsert_table,
    x_dataset_sync_enabled,
)
from naas_abi_marketplace.applications.x.pipelines.utils.build_media import (
    best_media_url,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _month_key(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m")


def _load_envelope(
    object_storage: ObjectStorageService, envelope_path: str
) -> dict[str, Any] | None:
    path = envelope_path.strip().lstrip("/")
    if "/" not in path:
        prefix, key = ENVELOPE_PREFIX, path
    else:
        prefix, key = split_key(path)
    try:
        raw = object_storage.get_object(prefix, key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"sync_envelope_paths: missing {envelope_path!r} ({exc})")
        return None
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        logger.warning(f"sync_envelope_paths: invalid JSON {envelope_path!r} ({exc})")
        return None
    return doc if isinstance(doc, dict) else None


def _media_rows(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (media_v1 rows, post_media_v1 rows) with pending downloads."""
    results = doc.get("results") or {}
    if not isinstance(results, dict):
        return [], []
    includes = results.get("includes") or {}
    media_list = includes.get("media") or []
    if not isinstance(media_list, list):
        return [], []

    media_by_key: dict[str, dict[str, Any]] = {}
    now = _utc_now()
    for record in media_list:
        if not isinstance(record, dict):
            continue
        media_key = str(record.get("media_key") or "").strip()
        if not media_key:
            continue
        source = best_media_url(record) or ""
        preview = str(record.get("preview_image_url") or "").strip()
        media_by_key[media_key] = {
            "media_key": media_key,
            "media_type": str(record.get("type") or ""),
            "source_url": source,
            "preview_url": preview,
            "status": "pending" if source else "failed",
            "storage_key": "",
            "sha256": "",
            "byte_size": 0,
            "last_error": "" if source else "no_downloadable_url",
            "updated_at": now,
        }

    post_media: list[dict[str, Any]] = []
    tweets = list(results.get("data") or []) + list(includes.get("tweets") or [])
    seen_pairs: set[tuple[str, str]] = set()
    for record in tweets:
        if not isinstance(record, dict):
            continue
        tweet_id = str(record.get("id") or "").strip()
        if not tweet_id:
            continue
        keys = (record.get("attachments") or {}).get("media_keys") or []
        for ordinal, media_key in enumerate(keys):
            mk = str(media_key or "").strip()
            if not mk or mk not in media_by_key:
                continue
            pair = (tweet_id, mk)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            post_media.append(
                {"tweet_id": tweet_id, "media_key": mk, "ordinal": ordinal}
            )
    return list(media_by_key.values()), post_media


def _count_bucket_rows(doc: dict[str, Any], envelope_path: str) -> list[dict[str, Any]]:
    """Map count-recent-tweets style envelopes when present."""
    results = doc.get("results") or {}
    if not isinstance(results, dict):
        return []
    data = results.get("data")
    if not isinstance(data, list) or not data:
        return []
    if not all(isinstance(row, dict) and "start" in row for row in data):
        return []
    query_slug = slugify(str(doc.get("query") or ""))
    rows: list[dict[str, Any]] = []
    for row in data:
        start = str(row.get("start") or "").strip()
        end = str(row.get("end") or "").strip()
        if not start or not end:
            continue
        rows.append(
            {
                "query_slug": query_slug,
                "bucket_start": start,
                "bucket_end": end,
                "tweet_count": int(row.get("tweet_count") or 0),
                "source_path": envelope_path,
            }
        )
    return rows


def _serialize_post_row(row: dict[str, Any]) -> dict[str, Any]:
    created = row["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return {
        "tweet_id": row["tweet_id"],
        "kind": row["kind"],
        "query_slug": row["query_slug"],
        "created_at": created,
        "created_month": _month_key(created),
        "author_id": row.get("author_id") or "",
        "text": row.get("text") or "",
        "full_text": row.get("full_text") or "",
        "lang": row.get("lang") or "",
        "conversation_id": row.get("conversation_id") or "",
        "like_count": int(row.get("like_count") or 0),
        "retweet_count": int(row.get("retweet_count") or 0),
        "reply_count": int(row.get("reply_count") or 0),
        "media_urls": row.get("media_urls") or "",
    }


def _serialize_author_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "author_id": row["author_id"],
        "username": row.get("username") or "",
        "display_name": row.get("display_name") or "",
        "description": row.get("description") or "",
        "location": row.get("location") or "",
        "verified_type": row.get("verified_type") or "",
        "verified": bool(row.get("verified")),
        "protected": bool(row.get("protected")),
        "is_identity_verified": bool(row.get("is_identity_verified")),
        "user_url": row.get("user_url") or "",
        "profile_image_url": row.get("profile_image_url") or "",
        "profile_banner_url": row.get("profile_banner_url") or "",
        "user_created_at": str(row.get("user_created_at") or ""),
        "most_recent_tweet_id": str(row.get("most_recent_tweet_id") or ""),
        "followers_count": int(row.get("followers_count") or 0),
        "following_count": int(row.get("following_count") or 0),
        "tweet_count": int(row.get("tweet_count") or 0),
        "listed_count": int(row.get("listed_count") or 0),
        "user_like_count": int(row.get("user_like_count") or 0),
        "media_count": int(row.get("media_count") or 0),
        "seen_at": str(row.get("seen_at") or ""),
    }


def sync_envelope_paths(
    module,
    envelope_paths: list[str],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Apply a bounded list of envelope object paths to the X datasets."""
    if not envelope_paths:
        return {"skipped": True, "reason": "no_paths"}
    if not x_dataset_sync_enabled(module):
        return {"skipped": True, "reason": "dataset_sync_disabled"}

    dataset = module.engine.services.dataset
    object_storage = module.engine.services.object_storage

    ingested = 0
    skipped = 0
    posts_written = 0
    authors_written = 0
    media_pending = 0

    batch_posts: list[dict[str, Any]] = []
    batch_authors: list[dict[str, Any]] = []
    batch_media: list[dict[str, Any]] = []
    batch_post_media: list[dict[str, Any]] = []
    batch_counts: list[dict[str, Any]] = []
    batch_envelopes: list[dict[str, Any]] = []
    now = _utc_now()

    for envelope_path in envelope_paths:
        path = str(envelope_path or "").strip()
        if not path:
            continue
        if not force and envelope_already_ingested(dataset, path):
            skipped += 1
            continue
        doc = _load_envelope(object_storage, path)
        if doc is None:
            skipped += 1
            continue

        post_rows, author_rows = parse_envelope(doc)
        batch_posts.extend(_serialize_post_row(row) for row in post_rows)
        batch_authors.extend(_serialize_author_row(row) for row in author_rows)
        media_rows, post_media_rows = _media_rows(doc)
        batch_media.extend(media_rows)
        batch_post_media.extend(post_media_rows)
        media_pending += sum(1 for row in media_rows if row.get("status") == "pending")
        batch_counts.extend(_count_bucket_rows(doc, path))

        query_slug = slugify(str(doc.get("query") or ""))
        batch_envelopes.append(
            {
                "envelope_path": path,
                "query_slug": query_slug,
                "ingested_at": now,
                "started_at": str(doc.get("started_at") or ""),
                "ended_at": str(doc.get("ended_at") or ""),
            }
        )
        ingested += 1

    posts_written = upsert_table(dataset, POSTS_V1, batch_posts)
    upsert_matched_tweet_ids_from_posts(dataset, batch_posts)
    authors_written = upsert_table(dataset, AUTHORS_V1, batch_authors)
    touched_author_ids = sorted(
        {
            str(row.get("author_id") or "").strip()
            for row in batch_posts
            if str(row.get("author_id") or "").strip()
        }
    )
    if touched_author_ids:
        recompute_author_stats(dataset, touched_author_ids)
    upsert_table(dataset, MEDIA_V1, batch_media)
    upsert_table(dataset, POST_MEDIA_V1, batch_post_media)
    upsert_table(dataset, COUNT_BUCKETS_V1, batch_counts)
    upsert_table(dataset, ENVELOPES_V1, batch_envelopes)

    commit_id = uuid.uuid4().hex
    upsert_table(
        dataset,
        PROJECTION_COMMITS_V1,
        [
            {
                "commit_id": commit_id,
                "committed_at": now,
                "envelope_count": ingested,
                "active": True,
                "detail": {
                    "paths": [row["envelope_path"] for row in batch_envelopes],
                    "posts": posts_written,
                    "authors": authors_written,
                },
            }
        ],
    )

    summary = {
        "ingested_envelopes": ingested,
        "skipped_envelopes": skipped,
        "posts_upserted": posts_written,
        "authors_upserted": authors_written,
        "media_pending": media_pending,
        "commit_id": commit_id,
    }
    logger.info(f"sync_envelope_paths: {summary}")
    if ingested > 0 or posts_written > 0 or authors_written > 0:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.read_cache import (
            publish_read_cache_generation,
        )

        publish_read_cache_generation(module, commit_id)
    return summary

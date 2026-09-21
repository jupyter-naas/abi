"""Resolve tweet media to app-served object-storage paths (download on demand)."""

from __future__ import annotations

import hashlib
import io
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_APP_PREFIX,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_worker import (
    DEFAULT_MAX_BYTES,
    _extension,
    _stream_download,
    download_and_store_media,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    MEDIA_V1,
    POST_MEDIA_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
    upsert_table,
)

MEDIA_HOSTS = {"pbs.twimg.com", "video.twimg.com"}
PUBLIC_MEDIA_PREFIX = "dataset/media"


def _escape(value: str) -> str:
    return value.replace("'", "''")


def public_media_rel(media_key: str, filename: str) -> str:
    return f"{PUBLIC_MEDIA_PREFIX}/{media_key}/{filename}"


def _filename_from_storage_key(storage_key: str) -> str:
    return storage_key.rsplit("/", 1)[-1]


def _media_rows_for_tweet(dataset, tweet_id: str) -> list[dict[str, Any]]:
    ensure_x_datasets(dataset)
    escaped = _escape(tweet_id)
    result = dataset.query(
        f"SELECT m.*, pm.ordinal "
        f"FROM {POST_MEDIA_V1} pm "
        f"INNER JOIN {MEDIA_V1} m ON pm.media_key = m.media_key "
        f"WHERE pm.tweet_id = '{escaped}' "
        f"ORDER BY pm.ordinal",
        namespace=X_DATASET_NAMESPACE,
    )
    return list(result.rows)


def _fallback_source_urls(dataset, tweet_id: str) -> list[str]:
    escaped = _escape(tweet_id)
    result = dataset.query(
        f"SELECT media_urls FROM {POSTS_V1} WHERE tweet_id = '{escaped}' LIMIT 1",
        namespace=X_DATASET_NAMESPACE,
    )
    if not result.rows:
        return []
    raw = str(result.rows[0].get("media_urls") or "")
    return [u for u in raw.split() if u.startswith("https://")]


def _download_legacy_urls(
    storage: ObjectStorageService,
    tweet_id: str,
    source_urls: list[str],
    *,
    max_bytes: int,
) -> list[str]:
    """Store under ``posts/by-id/{id}/media/`` (legacy artifact layout)."""
    rel_prefix = f"posts/by-id/{tweet_id}/media"
    storage_prefix = f"{DEFAULT_APP_PREFIX}/{rel_prefix}"
    paths: list[str] = []
    for source_url in source_urls:
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in MEDIA_HOSTS:
            continue
        try:
            body, content_type = _stream_download(source_url, max_bytes=max_bytes)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"X media resolve: legacy download failed ({exc})")
            continue
        digest = hashlib.sha256(body).hexdigest()
        filename = f"{digest}{_extension(content_type, source_url)}"
        storage.put_object_stream(storage_prefix, filename, io.BytesIO(body))
        paths.append(f"{rel_prefix}/{filename}")
    return paths


def ensure_media_row(
    dataset,
    storage: ObjectStorageService,
    row: dict[str, Any],
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> str | None:
    """Return a public relative path, downloading when still pending."""
    media_key = str(row.get("media_key") or "").strip()
    if not media_key:
        return None
    status = str(row.get("status") or "")
    storage_key = str(row.get("storage_key") or "")
    if status == "ready" and storage_key:
        return public_media_rel(media_key, _filename_from_storage_key(storage_key))

    source_url = str(row.get("source_url") or "").strip()
    if not source_url:
        return None
    now = datetime.now(UTC)
    try:
        storage_key, digest, size = download_and_store_media(
            storage,
            media_key=media_key,
            source_url=source_url,
            max_bytes=max_bytes,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"X media resolve: failed {media_key} ({exc})")
        upsert_table(
            dataset,
            MEDIA_V1,
            [
                {
                    "media_key": media_key,
                    "media_type": str(row.get("media_type") or ""),
                    "source_url": source_url,
                    "preview_url": str(row.get("preview_url") or ""),
                    "status": "failed",
                    "storage_key": "",
                    "sha256": "",
                    "byte_size": 0,
                    "last_error": str(exc)[:500],
                    "updated_at": now,
                }
            ],
        )
        return None

    upsert_table(
        dataset,
        MEDIA_V1,
        [
            {
                "media_key": media_key,
                "media_type": str(row.get("media_type") or ""),
                "source_url": source_url,
                "preview_url": str(row.get("preview_url") or ""),
                "status": "ready",
                "storage_key": storage_key,
                "sha256": digest,
                "byte_size": size,
                "last_error": "",
                "updated_at": now,
            }
        ],
    )
    return public_media_rel(media_key, _filename_from_storage_key(storage_key))


def ensure_tweet_media(
    dataset,
    storage: ObjectStorageService,
    tweet_id: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Download pending catalog media for a tweet; return served relative URLs."""
    if not tweet_id.isdigit():
        return {"tweet_id": tweet_id, "media_urls": "", "ready": False}

    paths: list[str] = []
    for row in _media_rows_for_tweet(dataset, tweet_id):
        rel = ensure_media_row(dataset, storage, row, max_bytes=max_bytes)
        if rel:
            paths.append(rel)

    if not paths:
        legacy = _fallback_source_urls(dataset, tweet_id)
        if legacy:
            paths = _download_legacy_urls(
                storage, tweet_id, legacy, max_bytes=max_bytes
            )

    return {
        "tweet_id": tweet_id,
        "media_urls": " ".join(paths),
        "ready": bool(paths),
    }


def object_storage_prefix_for_public_rel(rel: str) -> tuple[str, str] | None:
    """Map ``dataset/media/{key}/{file}`` to object-storage prefix + object name."""
    parts = rel.strip("/").split("/")
    if len(parts) != 4 or parts[0] != "dataset" or parts[1] != "media":
        return None
    media_key, filename = parts[2], parts[3]
    if not re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", media_key):
        return None
    if not re.fullmatch(r"[a-f0-9]{64}\.[a-z0-9]{1,5}", filename):
        return None
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
        MEDIA_OBJECT_PREFIX,
    )

    return f"{MEDIA_OBJECT_PREFIX}/{media_key}", filename

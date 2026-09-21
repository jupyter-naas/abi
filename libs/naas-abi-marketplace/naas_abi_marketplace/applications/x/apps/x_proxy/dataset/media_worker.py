"""Bounded, streamed media downloads for X Proxy dataset media rows."""

from __future__ import annotations

import hashlib
import io
import mimetypes
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    MEDIA_OBJECT_PREFIX,
    MEDIA_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
    upsert_table,
)

MEDIA_HOSTS = {"pbs.twimg.com", "video.twimg.com"}
DEFAULT_MAX_BYTES = 250 * 1024 * 1024


def _extension(content_type: str, source_url: str) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    extension = mimetypes.guess_extension(media_type) or ""
    if extension == ".jpe":
        extension = ".jpg"
    if not extension:
        suffix = urlparse(source_url).path.rsplit("/", 1)[-1].rsplit(".", 1)
        extension = f".{suffix[-1].lower()}" if len(suffix) == 2 else ".bin"
    return extension if re.fullmatch(r"\.[a-z0-9]{1,5}", extension) else ".bin"


def _stream_download(
    source_url: str,
    *,
    max_bytes: int,
) -> tuple[bytes, str]:
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in MEDIA_HOSTS:
        raise ValueError(f"rejected host for {source_url!r}")
    request = Request(source_url, headers={"User-Agent": "AXI-X-Proxy/1.0"})
    with urlopen(request, timeout=30) as response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or (final.hostname or "").lower() not in MEDIA_HOSTS:
            raise ValueError("redirect left approved X media hosts")
        content_type = str(response.headers.get("Content-Type") or "")
        if not content_type.startswith(("image/", "video/")):
            raise ValueError(f"unsupported content type {content_type!r}")
        buffer = io.BytesIO()
        while chunk := response.read(64 * 1024):
            buffer.write(chunk)
            if buffer.tell() > max_bytes:
                raise ValueError("media exceeds size limit")
    return buffer.getvalue(), content_type


def download_and_store_media(
    storage: ObjectStorageService,
    *,
    media_key: str,
    source_url: str,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[str, str, int]:
    """Stream download, upload via ``put_object_stream``, return storage key parts."""
    body, content_type = _stream_download(source_url, max_bytes=max_bytes)
    digest = hashlib.sha256(body).hexdigest()
    ext = _extension(content_type, source_url)
    filename = f"{digest}{ext}"
    prefix = f"{MEDIA_OBJECT_PREFIX}/{media_key}"
    storage.put_object_stream(prefix, filename, io.BytesIO(body))
    storage_key = f"{prefix}/{filename}"
    return storage_key, digest, len(body)


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def list_pending_media(
    dataset,
    *,
    limit: int = 50,
    max_age_days: int | None = 30,
) -> list[dict[str, Any]]:
    ensure_x_datasets(dataset)
    cutoff_sql = ""
    if max_age_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        cutoff_sql = f" AND updated_at >= TIMESTAMP '{cutoff.isoformat()}'"
    result = dataset.query(
        f"SELECT media_key, source_url, media_type FROM {MEDIA_V1} "
        f"WHERE status = 'pending' AND source_url <> ''{cutoff_sql} "
        f"ORDER BY updated_at LIMIT {int(limit)}",
        namespace=X_DATASET_NAMESPACE,
    )
    return list(result.rows)


def process_pending_media_batch(
    module,
    *,
    limit: int = 4,
    max_bytes: int | None = None,
    max_age_days: int | None = 30,
) -> dict[str, Any]:
    """Download up to *limit* pending media rows."""
    app_cfg = getattr(module.configuration, "app", None)
    dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
    if dataset_cfg is None or not getattr(dataset_cfg, "sync_enabled", False):
        return {"skipped": True, "reason": "dataset_sync_disabled"}

    dataset = module.engine.services.dataset
    storage = module.engine.services.object_storage
    byte_cap = max_bytes or int(getattr(dataset_cfg, "media_max_bytes", DEFAULT_MAX_BYTES))

    pending = list_pending_media(dataset, limit=limit, max_age_days=max_age_days)
    ready = 0
    failed = 0
    now = datetime.now(UTC)
    updates: list[dict[str, Any]] = []

    for row in pending:
        media_key = str(row.get("media_key") or "")
        source_url = str(row.get("source_url") or "")
        if not media_key or not source_url:
            continue
        try:
            storage_key, digest, size = download_and_store_media(
                storage,
                media_key=media_key,
                source_url=source_url,
                max_bytes=byte_cap,
            )
            updates.append(
                {
                    "media_key": media_key,
                    "media_type": str(row.get("media_type") or ""),
                    "source_url": source_url,
                    "preview_url": "",
                    "status": "ready",
                    "storage_key": storage_key,
                    "sha256": digest,
                    "byte_size": size,
                    "last_error": "",
                    "updated_at": now,
                }
            )
            ready += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"X media worker: failed {media_key} ({exc})")
            updates.append(
                {
                    "media_key": media_key,
                    "media_type": str(row.get("media_type") or ""),
                    "source_url": source_url,
                    "preview_url": "",
                    "status": "failed",
                    "storage_key": "",
                    "sha256": "",
                    "byte_size": 0,
                    "last_error": str(exc)[:500],
                    "updated_at": now,
                }
            )
            failed += 1

    upsert_table(dataset, MEDIA_V1, updates)
    return {"processed": len(pending), "ready": ready, "failed": failed}

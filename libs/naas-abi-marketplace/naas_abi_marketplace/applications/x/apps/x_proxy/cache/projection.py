"""Keep the Parquet read model in step with the ingest envelopes.

A refresh costs O(new envelopes), not O(history): the newest envelope timestamp
already projected is held in the key-value service, and only keys past it are
read. On a normal tick that is the four envelopes the search workflow wrote in
the last hour.

The watermark is also written into ``manifest.json``. Redis is the fast path;
if it is empty (restart, OOM) the manifest value is used rather than re-reading
the whole archive into RAM - that is what SIGKILL'd ``x_build_app``.

Everything lives in the platform's services - envelopes and Parquet in
``object_storage``, the watermark in ``kv``. Nothing is written to local disk, so
the projection survives a container replacement like any other published artifact.
"""

from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from naas_abi_core import logger
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.envelopes import (
    envelope_timestamp,
    parse_envelope,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.schema import (
    AUTHORS_KEY,
    CACHE_PREFIX,
    ENVELOPE_PREFIX,
    MANIFEST_KEY,
    SCHEMA_VERSION,
    WATERMARK_KEY,
    author_schema,
    partition_key,
    post_schema,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.storage import (
    split_key,
    walk,
)

# Envelopes are fetched concurrently inside a small batch: each is a separate
# object-storage GET. The batch bound is what keeps raw JSON off the heap -
# ``executor.map`` over the whole archive would hold every body at once.
FETCH_WORKERS = 8
FETCH_BATCH = 32


def _read_manifest(object_storage: ObjectStorageService) -> dict[str, Any]:
    try:
        raw = object_storage.get_object(CACHE_PREFIX, MANIFEST_KEY)
    except Exception:  # noqa: BLE001 - absent before the first build
        return {}
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _parse_watermark(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).strip())
    except ValueError:
        return None


def _read_watermark(kv: KeyValueService | None) -> datetime | None:
    if kv is None:
        return None
    try:
        raw = kv.get(WATERMARK_KEY)
    except Exception:  # noqa: BLE001 - treat any kv trouble as "no watermark"
        return None
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except UnicodeDecodeError:
        return None
    return _parse_watermark(text)


def _write_watermark(kv: KeyValueService | None, moment: datetime) -> None:
    if kv is None:
        return
    try:
        kv.set(WATERMARK_KEY, moment.isoformat().encode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - a lost watermark only costs a rescan
        logger.warning(f"X cache: could not store watermark ({exc})")


def _resolve_watermark(
    kv: KeyValueService | None,
    manifest: dict[str, Any],
    *,
    rebuild: bool,
) -> datetime | None:
    """KV first; manifest if Redis is empty. Never invent a watermark."""
    if rebuild:
        return None
    watermark = _read_watermark(kv)
    if watermark is not None:
        return watermark
    fallback = _parse_watermark(
        str(manifest["watermark"]) if manifest.get("watermark") else None
    )
    if fallback is not None:
        logger.info(
            f"X cache: Redis watermark missing - using manifest {fallback.isoformat()}"
        )
        # Put it back so the next tick does not have to read the manifest again.
        _write_watermark(kv, fallback)
    return fallback


def _envelope_keys(object_storage: ObjectStorageService) -> list[str]:
    """Every persisted envelope, across the per-query sub-prefixes."""
    return walk(object_storage, ENVELOPE_PREFIX, suffix=".json")


def _fetch_one(
    object_storage: ObjectStorageService, key: str
) -> tuple[str, bytes | None]:
    directory, name = split_key(key)
    try:
        return key, object_storage.get_object(directory, name)
    except Exception as exc:  # noqa: BLE001 - one bad object must not stop the run
        logger.warning(f"X cache: could not read {key} ({exc})")
        return key, None


def _project_batch(
    object_storage: ObjectStorageService,
    batch: list[tuple[str, datetime | None]],
) -> tuple[Any, Any, int, datetime | None]:
    """Fetch and parse one batch of envelopes into columnar frames.

    Returns ``(posts_frame, authors_frame, envelopes_read, newest_moment)``.
    JSON bodies are dropped as soon as the batch is parsed.
    """
    import polars as pl

    workers = min(FETCH_WORKERS, len(batch)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fetched = list(
            pool.map(lambda item: _fetch_one(object_storage, item[0]), batch)
        )

    post_rows: list[dict[str, Any]] = []
    author_rows: list[dict[str, Any]] = []
    newest: datetime | None = None
    read = 0
    for (key, body), (_key, moment) in zip(fetched, batch, strict=True):
        if body is None:
            continue
        try:
            posts, authors = parse_envelope(json.loads(body))
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning(f"X cache: could not parse {key} ({exc})")
            continue
        post_rows.extend(posts)
        author_rows.extend(authors)
        read += 1
        if moment is not None and (newest is None or moment > newest):
            newest = moment

    posts_frame = (
        pl.DataFrame(post_rows, schema=post_schema()).unique(
            subset=["tweet_id", "kind", "query_slug"], keep="last"
        )
        if post_rows
        else pl.DataFrame([], schema=post_schema())
    )
    authors_frame = (
        pl.DataFrame(author_rows, schema=author_schema())
        if author_rows
        else pl.DataFrame([], schema=author_schema())
    )
    return posts_frame, authors_frame, read, newest


def refresh(
    object_storage: ObjectStorageService,
    kv: KeyValueService | None = None,
    *,
    full: bool = False,
) -> dict[str, Any]:
    """Project any envelopes newer than the watermark into Parquet.

    *full* ignores the watermark and rebuilds from the whole archive - the
    recovery path for a schema change or a suspected gap. It rewrites partitions
    rather than appending, so it is safe to run repeatedly.

    Returns a summary; ``{"skipped": True}`` when there was nothing new.
    """
    import polars as pl

    manifest = _read_manifest(object_storage)
    stale_schema = int(manifest.get("schema_version") or 0) != SCHEMA_VERSION
    rebuild = full or stale_schema or not manifest
    if stale_schema and manifest:
        logger.info(
            f"X cache: manifest schema {manifest.get('schema_version')} != "
            f"{SCHEMA_VERSION} - rebuilding from the full archive"
        )

    watermark = _resolve_watermark(kv, manifest, rebuild=rebuild)
    # A published projection with no watermark at all would otherwise treat
    # every envelope as new and *append* a second copy of history. Replace.
    if not rebuild and watermark is None and manifest:
        rebuild = True
        logger.info(
            "X cache: no watermark in Redis or manifest - rebuilding "
            "(replace parts, do not append a full-archive dump)"
        )

    keys = _envelope_keys(object_storage)
    pending: list[tuple[str, datetime | None]] = []
    for key in keys:
        moment = envelope_timestamp(key)
        # An unreadable key is processed rather than skipped - better a redundant
        # read than a silently dropped tick.
        if watermark is not None and moment is not None and moment <= watermark:
            continue
        pending.append((key, moment))

    if not pending:
        logger.info(f"X cache: up to date ({len(keys):,} envelopes, none new)")
        return {"skipped": True, "envelopes_total": len(keys), "envelopes_new": 0}

    logger.info(
        f"X cache: projecting {len(pending):,} envelope(s) "
        f"({'full rebuild' if rebuild else f'since {watermark}'})"
    )

    posts_parts: list[Any] = []
    authors_parts: list[Any] = []
    newest = watermark
    read = 0
    for start in range(0, len(pending), FETCH_BATCH):
        batch = pending[start : start + FETCH_BATCH]
        posts, authors, batch_read, batch_newest = _project_batch(object_storage, batch)
        read += batch_read
        if not posts.is_empty():
            posts_parts.append(posts)
        if not authors.is_empty():
            authors_parts.append(authors)
        if batch_newest is not None and (newest is None or batch_newest > newest):
            newest = batch_newest
        done = start + len(batch)
        if done == len(pending) or done % (FETCH_BATCH * 4) == 0:
            logger.info(
                f"X cache: projected {done:,}/{len(pending):,} envelopes "
                f"({read:,} read)"
            )

    posts_frame = (
        pl.concat(posts_parts, how="vertical_relaxed").unique(
            subset=["tweet_id", "kind", "query_slug"], keep="last"
        )
        if posts_parts
        else pl.DataFrame([], schema=post_schema())
    )
    authors_frame = (
        pl.concat(authors_parts, how="vertical_relaxed")
        if authors_parts
        else pl.DataFrame([], schema=author_schema())
    )

    months_written = _write_posts(object_storage, posts_frame, rebuild=rebuild)
    authors_total = _write_authors(object_storage, authors_frame, rebuild=rebuild)

    if newest is not None:
        _write_watermark(kv, newest)

    summary = {
        "envelopes_total": len(keys),
        "envelopes_new": read,
        "posts_added": len(posts_frame),
        "authors_seen": authors_total,
        "months_written": months_written,
        "full_rebuild": rebuild,
        "watermark": newest.isoformat() if newest else None,
    }
    object_storage.put_object(
        CACHE_PREFIX,
        MANIFEST_KEY,
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "updated_at": datetime.now(UTC).isoformat(),
                **summary,
            }
        ).encode("utf-8"),
    )
    logger.info(f"X cache refresh: done - {summary}")
    return summary


def _write_posts(object_storage: ObjectStorageService, posts, *, rebuild: bool) -> int:
    """Append one part file per touched month (or replace them on a rebuild)."""
    import polars as pl

    if posts.is_empty():
        return 0
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    dated = posts.with_columns(pl.col("created_at").dt.strftime("%Y-%m").alias("_ym"))
    months = 0
    for (month,), part in dated.group_by(["_ym"], maintain_order=False):
        prefix = partition_key(str(month))
        frame = part.drop("_ym")
        if rebuild:
            # Collapse the month into a single file and drop whatever was there:
            # a rebuild is authoritative for every row it produces.
            for existing in _list_parts(object_storage, prefix):
                try:
                    object_storage.delete_object(prefix, existing)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        f"X cache: could not remove {prefix}/{existing} ({exc})"
                    )
        # Sorted with statistics so a window filter can skip row groups.
        buffer = io.BytesIO()
        frame.sort("created_at").write_parquet(
            buffer, compression="zstd", statistics=True
        )
        object_storage.put_object(prefix, f"part-{stamp}.parquet", buffer.getvalue())
        months += 1
    return months


def _list_parts(object_storage: ObjectStorageService, prefix: str) -> list[str]:
    return [split_key(k)[1] for k in walk(object_storage, prefix, suffix=".parquet")]


def _write_authors(
    object_storage: ObjectStorageService, authors, *, rebuild: bool
) -> int:
    """Upsert the author dimension: newest observation of each author wins."""
    import polars as pl

    if authors.is_empty() and not rebuild:
        return 0
    if not rebuild:
        try:
            existing = object_storage.get_object(CACHE_PREFIX, AUTHORS_KEY)
            authors = pl.concat(
                [pl.read_parquet(io.BytesIO(existing)), authors],
                how="vertical_relaxed",
            )
        except Exception as exc:  # noqa: BLE001 - absent before the first build
            logger.debug(f"X cache: no existing authors table to merge ({exc})")
    merged = authors.sort("seen_at").unique(subset=["author_id"], keep="last")
    buffer = io.BytesIO()
    merged.write_parquet(buffer, compression="zstd")
    object_storage.put_object(CACHE_PREFIX, AUTHORS_KEY, buffer.getvalue())
    return len(merged)

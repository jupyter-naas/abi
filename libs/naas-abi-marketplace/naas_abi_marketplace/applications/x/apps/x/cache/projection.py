"""Keep the Parquet read model in step with the ingest envelopes.

A refresh costs O(new envelopes), not O(history): the newest envelope timestamp
already projected is held in the key-value service, and only keys past it are
read. On a normal tick that is the four envelopes the search workflow wrote in
the last hour.

Everything lives in the platform's services — envelopes and Parquet in
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
from naas_abi_marketplace.applications.x.cache.envelopes import (
    envelope_timestamp,
    parse_envelope,
)
from naas_abi_marketplace.applications.x.cache.schema import (
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
from naas_abi_marketplace.applications.x.cache.storage import split_key, walk

# Envelopes are fetched concurrently: each is a separate object-storage GET, and
# the refresh is latency-bound rather than CPU-bound.
FETCH_WORKERS = 16


def _read_manifest(object_storage: ObjectStorageService) -> dict[str, Any]:
    try:
        raw = object_storage.get_object(CACHE_PREFIX, MANIFEST_KEY)
    except Exception:  # noqa: BLE001 — absent before the first build
        return {}
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _read_watermark(kv: KeyValueService | None) -> datetime | None:
    if kv is None:
        return None
    try:
        raw = kv.get(WATERMARK_KEY)
    except Exception:  # noqa: BLE001 — treat any kv trouble as "no watermark"
        return None
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _write_watermark(kv: KeyValueService | None, moment: datetime) -> None:
    if kv is None:
        return
    try:
        kv.set(WATERMARK_KEY, moment.isoformat().encode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — a lost watermark only costs a rescan
        logger.warning(f"X cache: could not store watermark ({exc})")


def _envelope_keys(object_storage: ObjectStorageService) -> list[str]:
    """Every persisted envelope, across the per-query sub-prefixes."""
    return walk(object_storage, ENVELOPE_PREFIX, suffix=".json")


def refresh(
    object_storage: ObjectStorageService,
    kv: KeyValueService | None = None,
    *,
    full: bool = False,
) -> dict[str, Any]:
    """Project any envelopes newer than the watermark into Parquet.

    *full* ignores the watermark and rebuilds from the whole archive — the
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
            f"{SCHEMA_VERSION} — rebuilding from the full archive"
        )

    watermark = None if rebuild else _read_watermark(kv)
    keys = _envelope_keys(object_storage)
    pending: list[tuple[str, datetime | None]] = []
    for key in keys:
        moment = envelope_timestamp(key)
        # An unreadable key is processed rather than skipped — better a redundant
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

    def _fetch(item: tuple[str, datetime | None]) -> tuple[str, bytes | None]:
        key, _moment = item
        directory, name = split_key(key)
        try:
            return key, object_storage.get_object(directory, name)
        except Exception as exc:  # noqa: BLE001 — one bad object must not stop the run
            logger.warning(f"X cache: could not read {key} ({exc})")
            return key, None

    post_rows: list[dict[str, Any]] = []
    author_rows: list[dict[str, Any]] = []
    newest = watermark
    read = 0
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        for (key, body), (_k, moment) in zip(
            pool.map(_fetch, pending), pending, strict=True
        ):
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

    # The same post arrives on many ticks; one row per (id, kind, query).
    posts_frame = pl.DataFrame(post_rows, schema=post_schema()).unique(
        subset=["tweet_id", "kind", "query_slug"], keep="last"
    )

    months_written = _write_posts(object_storage, posts_frame, rebuild=rebuild)
    authors_total = _write_authors(
        object_storage,
        pl.DataFrame(author_rows, schema=author_schema()),
        rebuild=rebuild,
    )

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
    logger.info(f"X cache refresh: done — {summary}")
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
        except Exception as exc:  # noqa: BLE001 — absent before the first build
            logger.debug(f"X cache: no existing authors table to merge ({exc})")
    merged = authors.sort("seen_at").unique(subset=["author_id"], keep="last")
    buffer = io.BytesIO()
    merged.write_parquet(buffer, compression="zstd")
    object_storage.put_object(CACHE_PREFIX, AUTHORS_KEY, buffer.getvalue())
    return len(merged)

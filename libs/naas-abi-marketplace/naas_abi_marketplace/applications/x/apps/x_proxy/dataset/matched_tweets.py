"""Materialized distinct ``tweet_id`` values that ever appear as ``kind = matched``."""

from __future__ import annotations

import threading
from typing import Any

from naas_abi_core import logger

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    MATCHED_TWEET_IDS_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    upsert_table,
)

_index_ready: bool | None = None
_rebuild_lock = threading.Lock()
_rebuild_started = False


def mark_matched_index_ready() -> None:
    global _index_ready
    _index_ready = True


def matched_index_ready(dataset) -> bool:
    """True when the materialized table has at least one row."""
    global _index_ready
    if _index_ready is True:
        return True
    result = dataset.query(
        f"SELECT 1 AS ok FROM {MATCHED_TWEET_IDS_V1} LIMIT 1",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    _index_ready = bool(result.rows)
    return _index_ready


def upsert_matched_tweet_ids_from_posts(
    dataset,
    post_rows: list[dict[str, Any]],
) -> int:
    """Extend the matched-id index from rows written in a sync batch."""
    ids = sorted(
        {
            str(row.get("tweet_id") or "").strip()
            for row in post_rows
            if str(row.get("kind") or "") == "matched" and str(row.get("tweet_id") or "").strip()
        }
    )
    if not ids:
        return 0
    written = upsert_table(dataset, MATCHED_TWEET_IDS_V1, [{"tweet_id": tid} for tid in ids])
    if written:
        mark_matched_index_ready()
    return written


def rebuild_matched_tweet_ids(dataset) -> int:
    """Full rebuild from ``posts_v1`` (one-time migration / repair)."""
    result = dataset.query(
        f"SELECT DISTINCT tweet_id FROM {POSTS_V1} "
        f"WHERE kind = 'matched' AND tweet_id <> ''",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    rows = [{"tweet_id": str(row["tweet_id"])} for row in result.rows if row.get("tweet_id")]
    if not rows:
        return 0
    dataset.write(
        MATCHED_TWEET_IDS_V1,
        rows,
        namespace=X_DATASET_NAMESPACE,
        mode="replace",
    )
    mark_matched_index_ready()
    logger.info(f"rebuild_matched_tweet_ids: {len(rows)} tweet_ids")
    return len(rows)


def _has_matched_posts(dataset) -> bool:
    result = dataset.query(
        f"SELECT 1 AS ok FROM {POSTS_V1} WHERE kind = 'matched' AND tweet_id <> '' LIMIT 1",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    return bool(result.rows)


def _rebuild_worker(dataset) -> None:
    try:
        rebuild_matched_tweet_ids(dataset)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"rebuild_matched_tweet_ids failed: {exc}")
    finally:
        global _rebuild_started
        _rebuild_started = False


def ensure_matched_tweet_ids_ready(dataset) -> None:
    """Kick off a background backfill when posts exist but the index is empty."""
    global _rebuild_started
    if matched_index_ready(dataset):
        return
    if not _has_matched_posts(dataset):
        return
    with _rebuild_lock:
        if _rebuild_started or matched_index_ready(dataset):
            return
        _rebuild_started = True
        thread = threading.Thread(target=_rebuild_worker, args=(dataset,), daemon=True)
        thread.start()

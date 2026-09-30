"""DuckLake file maintenance for the X read model.

Every sync batch commits a snapshot and adds small Parquet files (and delete
files, for upserts). Nothing merged them, so after a few weeks ``posts_v1`` sat
in ~3 400 files and ``authors_v1`` in ~400 with 70+ delete files: a one-row
lookup paid a filesystem round-trip per file (650 ms for an author by id, 20 ms
on the same rows in one file). Reads scale with *file count*, not rows, so this
has to run regularly - see ``XDatasetCompactionSchedule``.

Per table: flush inlined rows to Parquet, rewrite files whose rows are mostly
deleted, merge adjacent small files. Then, catalog-wide, expire snapshots older
than the retention window and delete the files only those snapshots used. Files
replaced by today's merge stay readable until their snapshots age out, so a
reader pinned to a recent snapshot never loses its data.
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

from naas_abi_core import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    TABLE_PRIMARY_KEYS,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)

CATALOG_ALIAS = "abi_datasets"
X_TABLES: tuple[str, ...] = tuple(TABLE_PRIMARY_KEYS)
DEFAULT_SNAPSHOT_RETENTION = timedelta(days=7)
# A file is rewritten once this share of its rows is deleted (DuckLake default
# is 0.95, which leaves upsert-heavy tables like ``authors_v1`` fragmented).
DEFAULT_DELETE_THRESHOLD = 0.1


def _file_count(dataset, table: str) -> int:
    result = dataset.query(
        f"SELECT count(*) AS n FROM ducklake_list_files('{CATALOG_ALIAS}', "
        f"'{table}', schema => '{X_DATASET_NAMESPACE}')",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    return int(result.rows[0]["n"]) if result.rows else 0


def _step(report: dict[str, Any], name: str, run) -> None:
    """Run one maintenance step; a failure is reported, not fatal.

    Sync keeps writing while this runs, so a step can lose a commit race - the
    next run picks it up, and the remaining steps are still worth doing.
    """
    started = time.perf_counter()
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"x dataset compaction: {name} failed ({exc})")
        report.setdefault("errors", []).append(f"{name}: {exc}")
    finally:
        report.setdefault("seconds", {})[name] = round(time.perf_counter() - started, 2)


def _compact_table(
    dataset, table: str, report: dict[str, Any], *, delete_threshold: float
) -> None:
    before = _file_count(dataset, table)
    _step(
        report,
        f"{table}.flush",
        lambda: dataset.flush(table, namespace=X_DATASET_NAMESPACE),
    )
    _step(
        report,
        f"{table}.rewrite",
        lambda: dataset.query(
            f"CALL ducklake_rewrite_data_files('{CATALOG_ALIAS}', '{table}', "
            f"schema => '{X_DATASET_NAMESPACE}', "
            f"delete_threshold => {float(delete_threshold)})",  # nosec B608
            namespace=X_DATASET_NAMESPACE,
        ),
    )
    _step(
        report,
        f"{table}.merge",
        lambda: dataset.compact(table, namespace=X_DATASET_NAMESPACE),
    )
    report["files"][table] = {"before": before, "after": _file_count(dataset, table)}
    logger.info(f"x dataset compaction: {table} {report['files'][table]}")


def compact_x_datasets(
    dataset,
    *,
    tables: tuple[str, ...] = X_TABLES,
    snapshot_retention: timedelta = DEFAULT_SNAPSHOT_RETENTION,
    delete_threshold: float = DEFAULT_DELETE_THRESHOLD,
) -> dict[str, Any]:
    """Compact the X tables and expire old snapshots; returns what it did."""
    ensure_x_datasets(dataset)
    report: dict[str, Any] = {"files": {}}
    for table in tables:
        _compact_table(dataset, table, report, delete_threshold=delete_threshold)

    hours = int(snapshot_retention.total_seconds() // 3600)
    _step(
        report,
        "expire_snapshots",
        lambda: dataset.query(
            f"CALL ducklake_expire_snapshots('{CATALOG_ALIAS}', "
            f"older_than => now() - INTERVAL {hours} HOUR)",  # nosec B608
            namespace=X_DATASET_NAMESPACE,
        ),
    )
    # Only files of snapshots expired above are scheduled for deletion.
    _step(
        report,
        "cleanup_old_files",
        lambda: dataset.query(
            f"CALL ducklake_cleanup_old_files('{CATALOG_ALIAS}', cleanup_all => true)",
            namespace=X_DATASET_NAMESPACE,
        ),
    )
    return report

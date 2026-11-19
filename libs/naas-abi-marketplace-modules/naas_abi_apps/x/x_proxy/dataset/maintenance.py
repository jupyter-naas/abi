"""DuckLake file maintenance for the X read model.

Every sync batch commits a snapshot and adds small Parquet files (and delete
files, for upserts). Nothing merged them, so after a few weeks ``posts_v1`` sat
in ~3 400 files and ``authors_v1`` in ~400 with 70+ delete files: a one-row
lookup paid a filesystem round-trip per file. Reads scale with *file count*,
not rows, so this runs regularly (the module's ``compact_dataset`` job).

Per table: ``flush`` (inlined rows to Parquet), then ``compact``, which
rewrites the files holding deleted rows and merges the small ones (core
``DatasetPort.compact``). Both are the dataset service's own calls on the
module's own tables, so a remote module may run them; the in-engine
``CALL ducklake_*`` SQL (file counts, a 0.1 delete threshold) is engine-only
and is gone. Expiring old snapshots and deleting the files nothing reads any
more is the engine's ``dataset_cleanup`` job, for the whole catalog.
"""

from __future__ import annotations

import time
from typing import Any

from naas_abi_apps.x.services import logger
from naas_abi_apps.x.x_proxy.dataset.store import (
    TABLE_PRIMARY_KEYS,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)

X_TABLES: tuple[str, ...] = tuple(TABLE_PRIMARY_KEYS)


def _step(report: dict[str, Any], name: str, run) -> bool:
    """Run one maintenance step; a failure is reported, not fatal.

    Sync keeps writing while this runs, so a step can lose a commit race - the
    next run picks it up, and the remaining tables are still worth doing.
    """
    started = time.perf_counter()
    try:
        run()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"x dataset compaction: {name} failed ({exc})")
        report.setdefault("errors", []).append(f"{name}: {exc}")
        return False
    finally:
        report["seconds"][name] = round(time.perf_counter() - started, 2)


def compact_x_datasets(
    dataset,
    *,
    tables: tuple[str, ...] = X_TABLES,
) -> dict[str, Any]:
    """Flush then compact each X table; returns what it did.

    ``dataset`` is the blocking dataset service (``SyncModule``'s
    ``engine.services.dataset``): call this from a worker thread. A failed
    flush skips that table's compaction (core's maintenance job does the same);
    a failed step never stops the other tables.
    """
    ensure_x_datasets(dataset)
    report: dict[str, Any] = {"tables": [], "seconds": {}}
    for table in tables:
        flushed = _step(
            report,
            f"{table}.flush",
            lambda table=table: dataset.flush(table, namespace=X_DATASET_NAMESPACE),
        )
        if flushed:
            _step(
                report,
                f"{table}.compact",
                lambda table=table: dataset.compact(
                    table, namespace=X_DATASET_NAMESPACE
                ),
            )
        report["tables"].append(table)
    logger.info(f"x dataset compaction: done - {report}")
    return report

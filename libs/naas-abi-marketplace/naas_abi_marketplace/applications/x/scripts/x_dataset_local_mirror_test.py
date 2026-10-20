"""Local prod-mirror gate: full backfill, idempotency, row counts, cache compare."""

from __future__ import annotations

import argparse
import json
import logging
import resource
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_kb = usage.ru_maxrss
    if rss_kb > 10_000_000:
        return round(rss_kb / (1024 * 1024), 2)
    return round(rss_kb / 1024, 2)


def _table_counts(module) -> dict[str, int]:
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
        AUTHORS_V1,
        ENVELOPES_V1,
        MEDIA_V1,
        POSTS_V1,
        X_DATASET_NAMESPACE,
        ensure_x_datasets,
    )

    dataset = module.engine.services.dataset
    ensure_x_datasets(dataset)
    out: dict[str, int] = {}
    for table in (POSTS_V1, AUTHORS_V1, ENVELOPES_V1, MEDIA_V1):
        result = dataset.query(
            f"SELECT COUNT(*) AS n FROM {table}",
            namespace=X_DATASET_NAMESPACE,
        )
        out[table] = int(result.rows[0]["n"]) if result.rows else 0
    return out


def _run_backfill(module, *, batch_size: int) -> dict:
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.envelope_paths import (
        ENVELOPE_PREFIX,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.storage_walk import (
        walk,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.sync import (
        sync_envelope_paths,
    )

    storage = module.engine.services.object_storage
    paths = walk(storage, ENVELOPE_PREFIX, suffix=".json")
    paths.sort()
    started = time.monotonic()
    ingested = 0
    skipped = 0
    for offset in range(0, len(paths), batch_size):
        batch = paths[offset : offset + batch_size]
        summary = sync_envelope_paths(module, batch)
        ingested += int(summary.get("ingested_envelopes") or 0)
        skipped += int(summary.get("skipped_envelopes") or 0)
        logger.info(
            "Backfill progress %s/%s envelopes (ingested=%s skipped=%s)",
            min(offset + batch_size, len(paths)),
            len(paths),
            ingested,
            skipped,
        )
    return {
        "envelopes": len(paths),
        "ingested_envelopes": ingested,
        "skipped_envelopes": skipped,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.local.yaml"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--skip-second-pass",
        action="store_true",
        help="Skip idempotent re-run (faster smoke).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x import ABIModule

    started = time.monotonic()
    engine = Engine(configuration=args.config.read_text(encoding="utf-8"))
    engine.load()
    module = ABIModule.get_instance()

    logger.info("Pass 1: full mirror backfill")
    pass1 = _run_backfill(module, batch_size=args.batch_size)
    after_first = _table_counts(module)
    logger.info("Pass 1 summary: %s", pass1)
    logger.info("Row counts after pass 1: %s", after_first)

    pass2 = None
    if not args.skip_second_pass:
        logger.info("Pass 2: idempotency (expect skipped envelopes, stable counts)")
        pass2 = _run_backfill(module, batch_size=args.batch_size)
        logger.info("Pass 2 summary: %s", pass2)
    after_second = _table_counts(module)
    logger.info("Row counts after pass 2: %s", after_second)

    cache_compare: dict | None = None
    try:
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.api import (
            graph_totals,
        )

        totals = graph_totals(module.engine.services.dataset)
        cache_compare = {
            "dataset_graph_totals": totals,
            "dataset_posts_rows": after_second.get("posts_v1", 0),
        }
        logger.info("Dataset totals: %s", cache_compare)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache compare skipped (%s)", exc)

    report = {
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_mb": _peak_rss_mb(),
        "pass1": pass1,
        "pass2": pass2,
        "row_counts": after_second,
        "cache_compare": cache_compare,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

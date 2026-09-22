"""Stream local envelope archive into X Dataset Service (mirror / prod import prep)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from naas_abi_core.utils.Logger import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.envelope_paths import (
    ENVELOPE_PREFIX,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.storage_walk import walk
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.sync import (
    sync_envelope_paths,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.local.yaml"),
        help="ABI YAML config (loads Engine before sync).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Envelope paths per sync call (bounded memory).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max envelopes to process (0 = all).",
    )
    parser.add_argument(
        "--paths-file",
        type=Path,
        help="Optional newline-delimited envelope paths (relative object keys).",
    )
    parser.add_argument(
        "--pending-from-audit",
        action="store_true",
        help=(
            "Sync only envelope paths reported as pending_ingest by "
            "audit_envelope_bookkeeping (no paths-file needed)."
        ),
    )
    parser.add_argument(
        "--staging-prefix",
        default="x/dataset_import/batches",
        help="Object-storage prefix for checksum manifest batches (prod import).",
    )
    parser.add_argument(
        "--write-staging",
        action="store_true",
        help="Write JSON batch manifests under staging-prefix after each batch.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest envelopes even when already recorded in envelopes_v1.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x import ABIModule

    engine = Engine(configuration=args.config.read_text(encoding="utf-8"))
    engine.load()
    module = ABIModule.get_instance()
    object_storage = module.engine.services.object_storage

    if args.pending_from_audit:
        if not module.engine.services.dataset_available():
            raise SystemExit(
                "Dataset Service is not available (--pending-from-audit)."
            )
        from signals.x.apps.x_proxy.dataset.envelope_bookkeeping import (
            envelope_bookkeeping_diff,
        )

        report = envelope_bookkeeping_diff(
            object_storage, module.engine.services.dataset
        )
        paths = list(report.get("pending_ingest") or [])
        logger.info(f"backfill_x_datasets: {len(paths)} pending path(s) from audit")
    elif args.paths_file:
        if not args.paths_file.is_file():
            raise SystemExit(f"paths-file not found: {args.paths_file.resolve()}")
        paths = [
            line.strip()
            for line in args.paths_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        paths = walk(object_storage, ENVELOPE_PREFIX, suffix=".json")
        paths.sort()

    if args.limit:
        paths = paths[: args.limit]

    total = len(paths)
    logger.info(f"backfill_x_datasets: {total} envelope path(s) to sync")
    started = time.monotonic()
    processed = 0
    summaries: list[dict] = []

    for offset in range(0, total, args.batch_size):
        batch = paths[offset : offset + args.batch_size]
        summary = sync_envelope_paths(module, batch, force=args.force)
        summaries.append(summary)
        processed += len(batch)
        if args.write_staging:
            manifest = {
                "batch_offset": offset,
                "batch_size": len(batch),
                "paths": batch,
                "summary": summary,
            }
            key = f"batch_{offset:08d}.json"
            object_storage.put_object(
                args.staging_prefix.rstrip("/"),
                key,
                json.dumps(manifest, separators=(",", ":")).encode("utf-8"),
            )
        logger.info(f"backfill_x_datasets: {processed}/{total} envelopes")

    elapsed = time.monotonic() - started
    report = {
        "envelopes": total,
        "elapsed_seconds": round(elapsed, 3),
        "batches": len(summaries),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

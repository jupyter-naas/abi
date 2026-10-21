"""Compact the X Dataset Service tables and expire old DuckLake snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.maintenance import (
    DEFAULT_DELETE_THRESHOLD,
    DEFAULT_SNAPSHOT_RETENTION,
    X_TABLES,
    compact_x_datasets,
)
from naas_abi_marketplace.applications.x.scripts._engine_bootstrap import load_engine


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="ABI YAML config (default: config.{ENV}.yaml or config.yaml).",
    )
    parser.add_argument(
        "--table",
        action="append",
        choices=X_TABLES,
        help="Only this table (repeatable). Default: every X table.",
    )
    parser.add_argument(
        "--retention-days",
        type=float,
        default=DEFAULT_SNAPSHOT_RETENTION.total_seconds() / 86400,
        help="Keep snapshots (time travel) newer than this many days.",
    )
    parser.add_argument(
        "--delete-threshold",
        type=float,
        default=DEFAULT_DELETE_THRESHOLD,
        help="Rewrite a file once this share of its rows is deleted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    from naas_abi_marketplace.applications.x import ABIModule

    engine = load_engine(args.config)
    engine.load()
    module = ABIModule.get_instance()
    if not module.engine.services.dataset_available():
        raise SystemExit("Dataset Service is not available.")
    report = compact_x_datasets(
        module.engine.services.dataset,
        tables=tuple(args.table) if args.table else X_TABLES,
        snapshot_retention=timedelta(days=args.retention_days),
        delete_threshold=args.delete_threshold,
    )
    print(json.dumps(report, indent=2))
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())

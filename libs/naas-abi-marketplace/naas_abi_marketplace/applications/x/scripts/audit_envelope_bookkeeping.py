#!/usr/bin/env python3
"""Read-only audit: ``x/search_recent_tweets`` envelopes vs ``x.envelopes_v1``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from signals.x.apps.x_proxy.cache.schema import ENVELOPE_PREFIX
from signals.x.apps.x_proxy.dataset.envelope_bookkeeping import (
    envelope_bookkeeping_diff,
)


def _services_from_config(config_path: Path):
    src_root = Path(__file__).resolve().parents[3]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x import ABIModule

    engine = Engine(configuration=config_path.read_text(encoding="utf-8"))
    engine.load()
    module = ABIModule.get_instance()
    if not module.engine.services.dataset_available():
        raise SystemExit(
            "Dataset Service is not available. Enable services.dataset in ABI config."
        )
    return module.engine.services.object_storage, module.engine.services.dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Report search_recent_tweets envelope JSON in object storage that are "
            "not recorded in x.envelopes_v1, and ingested paths missing from storage."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.local.yaml"),
        help="ABI config file.",
    )
    parser.add_argument(
        "--envelope-prefix",
        default=ENVELOPE_PREFIX,
        help=f"Envelope tree prefix (default: {ENVELOPE_PREFIX}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full report as JSON.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when pending_ingest or ingested_not_in_storage is non-empty.",
    )
    args = parser.parse_args()

    config_path = args.config.resolve()
    if not config_path.is_file():
        raise SystemExit(f"Config not found: {config_path}")

    object_storage, dataset = _services_from_config(config_path)
    report = envelope_bookkeeping_diff(
        object_storage,
        dataset,
        envelope_prefix=args.envelope_prefix,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        prefix = report["envelope_prefix"]
        print(f"Envelope bookkeeping ({prefix})")
        print(f"  Object storage: {report['storage_envelope_count']} envelope(s)")
        print(f"  envelopes_v1: {report['ingested_envelope_count']} row(s)")
        pending = report["pending_ingest"]
        orphans = report["ingested_not_in_storage"]
        if pending:
            print(f"  Pending ingest ({len(pending)}): {', '.join(pending[:5])}")
            if len(pending) > 5:
                print(f"    … and {len(pending) - 5} more")
        else:
            print("  Pending ingest: none")
        if orphans:
            print(
                f"  Ingested but missing from storage ({len(orphans)}): "
                f"{', '.join(orphans[:5])}"
            )
            if len(orphans) > 5:
                print(f"    … and {len(orphans) - 5} more")
        else:
            print("  Ingested but missing from storage: none")
        print(f"  In sync: {report['in_sync']}")

    if args.strict and not report["in_sync"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

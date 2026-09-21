#!/usr/bin/env python3
"""Replay staged import batch manifests into production Dataset Service."""

from __future__ import annotations

import argparse
import json
import sys

from naas_abi_core.utils.Logger import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.sync import (
    sync_envelope_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staging-prefix",
        default="x/dataset_import/batches",
        help="Object-storage prefix written by backfill_x_datasets --write-staging.",
    )
    parser.add_argument(
        "--limit-batches",
        type=int,
        default=0,
        help="Process at most N batch manifests (0 = all).",
    )
    args = parser.parse_args()

    from naas_abi_marketplace.applications.x import ABIModule

    module = ABIModule.get_instance()
    storage = module.engine.services.object_storage
    prefix = args.staging_prefix.rstrip("/")
    keys = sorted(
        name
        for name in storage.list_objects(prefix)
        if name.endswith(".json") and not name.endswith("/")
    )
    if args.limit_batches:
        keys = keys[: args.limit_batches]

    applied = 0
    for key in keys:
        raw = storage.get_object(prefix, key)
        manifest = json.loads(raw.decode("utf-8"))
        paths = manifest.get("paths") or []
        summary = sync_envelope_paths(module, paths)
        logger.info(f"import_x_dataset_batches: {key} -> {summary}")
        applied += 1

    print(json.dumps({"batches": applied}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

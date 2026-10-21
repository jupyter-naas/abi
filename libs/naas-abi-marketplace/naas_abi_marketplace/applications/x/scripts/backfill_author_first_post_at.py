"""Stamp ``author_stats_v1.first_post_at`` from the posts table (one-shot).

Earliest tweet per author is ``MIN(created_at)`` — the SQL form of sort by
``created_at`` and drop-duplicates on ``author_id``. New authors get the field
on ingest; this CLI fills rows created before that column existed.

Does not re-ingest envelopes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.author_stats import (
    count_authors_missing_first_post,
    stamp_missing_first_post_at_from_posts,
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
        "--dry-run",
        action="store_true",
        help="Count null first_post_at rows and exit without writing.",
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
    dataset = module.engine.services.dataset
    missing_before = count_authors_missing_first_post(dataset)
    report: dict[str, object] = {
        "dry_run": bool(args.dry_run),
        "missing_before": missing_before,
    }
    if args.dry_run:
        print(json.dumps(report, indent=2))
        return 0
    stamped = stamp_missing_first_post_at_from_posts(dataset)
    report["stamped"] = stamped
    report["missing_after"] = count_authors_missing_first_post(dataset)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

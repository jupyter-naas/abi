#!/usr/bin/env python3
"""Compare dataset post counts vs Parquet cache for local mirror validation."""

from __future__ import annotations

import argparse
import json
import sys

from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.reader import CacheReader
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    module = ABIModule.get_instance()
    storage = module.engine.services.object_storage
    dataset = module.engine.services.dataset
    ensure_x_datasets(dataset)

    cache = CacheReader(storage)
    cache_total, _ = cache.search_tweets("", offset=0, limit=1)
    ds = dataset.query(
        f"SELECT COUNT(*) AS n FROM {POSTS_V1}",
        namespace=X_DATASET_NAMESPACE,
    )
    dataset_total = int(ds.rows[0]["n"]) if ds.rows else 0
    report = {
        "cache_search_total": cache_total,
        "dataset_posts_total": dataset_total,
        "delta": dataset_total - cache_total,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

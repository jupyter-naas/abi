"""One-off audit: dataset posts vs Parquet cache canonical counts."""

from __future__ import annotations

from pathlib import Path

from naas_abi_core.engine.Engine import Engine

from naas_abi_marketplace.applications.x.apps.x_proxy.cache.projection import (
    _read_processed_envelopes,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.reader import CacheReader
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.schema import (
    ENVELOPE_PREFIX,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.cache.storage import walk
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import api as ds_api
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHORS_V1,
    AUTHOR_STATS_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
)

def main() -> None:
    engine = Engine(
        configuration=Path("config.local.yaml").read_text(encoding="utf-8")
    )
    engine.load()
    ds = engine.services.dataset
    ns = X_DATASET_NAMESPACE

    def q(sql: str) -> int:
        rows = ds.query(sql, namespace=ns).rows
        return int(rows[0]["n"]) if rows else 0

    print("posts_rows", q(f"SELECT COUNT(*) AS n FROM {POSTS_V1}"))
    print("posts_distinct_tweet_id", q(f"SELECT COUNT(DISTINCT tweet_id) AS n FROM {POSTS_V1}"))
    print(
        "posts_bad_tweet_id_rows",
        q(
            f"SELECT COUNT(*) AS n FROM {POSTS_V1} "
            "WHERE tweet_id IS NULL OR trim(tweet_id) = '' "
            "OR NOT regexp_full_match(tweet_id, '^[0-9]+$')"
        ),
    )
    print("dataset_graph_totals", ds_api.graph_totals(ds))
    print("authors_v1_rows", q(f"SELECT COUNT(*) AS n FROM {AUTHORS_V1}"))
    print("author_stats_rows", q(f"SELECT COUNT(*) AS n FROM {AUTHOR_STATS_V1}"))

    storage = engine.services.object_storage
    all_env = walk(storage, ENVELOPE_PREFIX, suffix=".json")
    processed = _read_processed_envelopes(storage)
    print("envelopes_total", len(all_env))
    print("parquet_processed_envelopes", len(processed))

    cr = CacheReader(storage)
    cache_total, _ = cr.search_tweets("", offset=0, limit=1)
    print("cache_search_tweets_total", cache_total)


if __name__ == "__main__":
    main()

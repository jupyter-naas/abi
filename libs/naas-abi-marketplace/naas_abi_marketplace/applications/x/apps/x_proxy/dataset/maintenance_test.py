"""DuckLake compaction of the X tables."""

from __future__ import annotations

from datetime import UTC, datetime

from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import api as ds_api
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.maintenance import (
    compact_x_datasets,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    POSTS_V1,
    upsert_table,
)


def _post(tweet_id: str, now: datetime) -> dict:
    return {
        "tweet_id": tweet_id,
        "kind": "matched",
        "query_slug": "q",
        "created_at": now,
        "created_month": now.strftime("%Y-%m"),
        "author_id": "a1",
        "text": f"post {tweet_id}",
        "full_text": f"post {tweet_id}",
        "lang": "en",
        "conversation_id": "",
        "like_count": 0,
        "retweet_count": 0,
        "reply_count": 0,
        "media_urls": "",
    }


def test_compaction_merges_small_files_and_keeps_every_row(tmp_path) -> None:
    # No inlining, so every batch lands as its own Parquet file.
    dataset = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}",
        str(tmp_path / "warehouse"),
        data_inlining_row_limit=0,
    )
    now = datetime.now(UTC)
    for batch in range(6):
        upsert_table(dataset, POSTS_V1, [_post(str(1000 + batch), now)])

    report = compact_x_datasets(dataset, tables=(POSTS_V1,))

    assert "errors" not in report, report
    files = report["files"][POSTS_V1]
    assert files["before"] >= 6
    assert files["after"] < files["before"]
    total, _ = ds_api.search_tweets(dataset, "")
    assert total == 6

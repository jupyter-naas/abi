"""Compaction of the X tables (flush + compact per table)."""

from __future__ import annotations

from datetime import UTC, datetime

from naas_abi_apps.x.x_proxy.dataset import api as ds_api
from naas_abi_apps.x.x_proxy.dataset.maintenance import (
    X_TABLES,
    compact_x_datasets,
)
from naas_abi_apps.x.x_proxy.dataset.store import (
    AUTHORS_V1,
    POSTS_V1,
    upsert_table,
)
from naas_abi_apps.x.x_proxy.testing import FakeDataset


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


def test_compaction_flushes_then_compacts_each_table_and_keeps_every_row() -> None:
    dataset = FakeDataset()
    now = datetime.now(UTC)
    for batch in range(6):
        upsert_table(dataset, POSTS_V1, [_post(str(1000 + batch), now)])

    report = compact_x_datasets(dataset)

    assert "errors" not in report, report
    assert report["tables"] == list(X_TABLES)
    assert dataset.maintenance[:2] == [("flush", POSTS_V1), ("compact", POSTS_V1)]
    assert len(dataset.maintenance) == 2 * len(X_TABLES)
    # No engine-only SQL: compaction is the dataset service's own calls.
    assert not any("ducklake" in sql.lower() for sql in dataset.queries)
    total, _ = ds_api.search_tweets(dataset, "")
    assert total == 6


def test_a_failed_flush_skips_that_tables_compaction_only() -> None:
    dataset = FakeDataset()
    flush = dataset.flush

    def failing_flush(name, *, namespace="default"):
        if name == POSTS_V1:
            raise RuntimeError("commit conflict")
        return flush(name, namespace=namespace)

    dataset.flush = failing_flush
    report = compact_x_datasets(dataset)
    assert report["errors"] == [f"{POSTS_V1}.flush: commit conflict"]
    assert ("compact", POSTS_V1) not in dataset.maintenance
    assert ("compact", AUTHORS_V1) in dataset.maintenance

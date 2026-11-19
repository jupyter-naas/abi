"""Materialized matched tweet id index."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from naas_abi_apps.x.x_proxy.dataset import api as ds_api
from naas_abi_apps.x.x_proxy.dataset import matched_tweets, store
from naas_abi_apps.x.x_proxy.dataset.matched_tweets import (
    rebuild_matched_tweet_ids,
)
from naas_abi_apps.x.x_proxy.dataset.store import (
    MATCHED_TWEET_IDS_V1,
    POSTS_V1,
    ensure_x_datasets,
    upsert_table,
)
from naas_abi_apps.x.x_proxy.testing import FakeDataset
from naas_abi_sdk.services.errors import ServiceError


@pytest.fixture
def dataset(tmp_path):
    return FakeDataset()


def test_rebuild_matched_tweet_ids_enables_canonical_dedup(dataset) -> None:
    ensure_x_datasets(dataset)
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            {
                "tweet_id": "1",
                "kind": "matched",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a1",
                "text": "m",
                "full_text": "m",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            },
            {
                "tweet_id": "1",
                "kind": "referenced",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a1",
                "text": "r",
                "full_text": "r",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            },
        ],
    )
    assert rebuild_matched_tweet_ids(dataset) == 1
    ensure_x_datasets(dataset)
    totals = ds_api.graph_totals(dataset)
    assert totals["posts"] == 1


def _matched_post(tweet_id: str) -> dict:
    return {
        "tweet_id": tweet_id,
        "kind": "matched",
        "query_slug": "q",
        "created_at": datetime.now(UTC),
        "created_month": "2026-09",
        "author_id": "a1",
        "text": "m",
        "full_text": "m",
        "lang": "en",
        "conversation_id": "",
        "like_count": 0,
        "retweet_count": 0,
        "reply_count": 0,
        "media_urls": "",
    }


class Flaky:
    """Another dataset service object over the same tables, whose queries of the
    matched-id index fail while ``fail`` is set."""

    def __init__(self, inner: FakeDataset) -> None:
        self.inner, self.fail = inner, True

    def query(self, sql: str, **kwargs):
        if self.fail and MATCHED_TWEET_IDS_V1 in sql:
            raise ServiceError("UNAVAILABLE", "dataset service restarting")
        return self.inner.query(sql, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self.inner, name)


def _wait_for_index() -> None:
    deadline = time.monotonic() + 5
    while matched_tweets._index_ready is not True and time.monotonic() < deadline:
        time.sleep(0.01)
    assert matched_tweets._index_ready is True


def test_a_transient_index_error_does_not_disable_the_backfill(
    dataset, monkeypatch
) -> None:
    upsert_table(dataset, POSTS_V1, [_matched_post("1")])
    flaky = Flaky(dataset)

    ensure_x_datasets(flaky)  # the index check fails: logged, not raised
    assert flaky not in store._ensured

    flaky.fail = False
    ensure_x_datasets(flaky)  # within INDEX_RECHECK_SECONDS: not looked at again
    assert matched_tweets._index_ready is not True

    monkeypatch.setattr(store, "INDEX_RECHECK_SECONDS", 0.0)
    ensure_x_datasets(flaky)  # starts the backfill
    _wait_for_index()
    ensure_x_datasets(flaky)
    assert flaky in store._ensured
    assert dataset.query(f"SELECT tweet_id FROM {MATCHED_TWEET_IDS_V1}").rows == [
        {"tweet_id": "1"}
    ]


def test_a_failed_backfill_starts_again_after_its_backoff(dataset, monkeypatch) -> None:
    upsert_table(dataset, POSTS_V1, [_matched_post("1")])
    other = Flaky(dataset)
    other.fail = False
    monkeypatch.setattr(store, "INDEX_RECHECK_SECONDS", 0.0)
    real_rebuild = matched_tweets.rebuild_matched_tweet_ids
    runs: list[int] = []

    def rebuild(ds):
        runs.append(1)
        if len(runs) == 1:
            raise ServiceError("UNAVAILABLE", "dataset service restarting")
        return real_rebuild(ds)

    monkeypatch.setattr(matched_tweets, "rebuild_matched_tweet_ids", rebuild)

    ensure_x_datasets(other)
    deadline = time.monotonic() + 5
    while matched_tweets._rebuild_failed_at is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert other not in store._ensured
    ensure_x_datasets(other)  # within REBUILD_RETRY_SECONDS: not started again
    assert runs == [1]

    monkeypatch.setattr(matched_tweets, "REBUILD_RETRY_SECONDS", 0.0)
    ensure_x_datasets(other)
    _wait_for_index()
    assert len(runs) == 2

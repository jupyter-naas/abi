"""Materialized matched tweet id index."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import api as ds_api
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.matched_tweets import (
    rebuild_matched_tweet_ids,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    POSTS_V1,
    ensure_x_datasets,
    upsert_table,
)


@pytest.fixture
def dataset(tmp_path):
    return DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}",
        str(tmp_path / "warehouse"),
    )


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

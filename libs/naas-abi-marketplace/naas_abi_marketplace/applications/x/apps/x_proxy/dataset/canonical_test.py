"""Canonical projection counts (match-wins, one row per tweet)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import api as ds_api
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHORS_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    ensure_x_datasets,
    upsert_table,
)


@pytest.fixture
def dataset(tmp_path):
    return DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}",
        str(tmp_path / "warehouse"),
    )


def test_graph_totals_dedupes_referenced_when_matched_exists(dataset) -> None:
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
            {
                "tweet_id": "2",
                "kind": "referenced",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a1",
                "text": "ctx",
                "full_text": "ctx",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            },
        ],
    )
    upsert_table(
        dataset,
        AUTHORS_V1,
        [
            {
                "author_id": "a1",
                "username": "alice",
                "display_name": "Alice",
                "description": "",
                "location": "",
                "verified_type": "",
                "verified": False,
                "protected": False,
                "is_identity_verified": False,
                "user_url": "",
                "profile_image_url": "",
                "profile_banner_url": "",
                "user_created_at": "",
                "most_recent_tweet_id": "",
                "followers_count": 0,
                "following_count": 0,
                "tweet_count": 0,
                "listed_count": 0,
                "user_like_count": 0,
                "media_count": 0,
                "seen_at": now,
            }
        ],
    )
    totals = ds_api.graph_totals(dataset)
    assert totals == {"posts": 2, "matched": 1, "referenced": 1}
    user_total, users = ds_api.search_users(dataset, "", limit=10)
    assert user_total == 1
    assert users[0]["username"] == "alice"
    tweet_total, _ = ds_api.search_tweets(dataset, "", limit=10)
    assert tweet_total == 2

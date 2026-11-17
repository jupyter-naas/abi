"""Author stats cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_apps.x.x_proxy.dataset.author_stats import (
    merge_profile_with_stats,
    profile_stats,
)
from naas_abi_apps.x.x_proxy.dataset.store import (
    AUTHOR_STATS_V1,
    POSTS_V1,
    ensure_x_datasets,
    upsert_table,
)
from naas_abi_apps.x.x_proxy.testing import FakeDataset


@pytest.fixture
def dataset():
    return FakeDataset()


def test_merge_profile_with_stats_exposes_first_post_at() -> None:
    profile = merge_profile_with_stats(
        {"username": "pilot1", "author_id": "42"},
        {
            "matched_count": 2,
            "referenced_count": 1,
            "first_post_at": "2024-01-01T00:00:00+00:00",
            "last_post_at": "2025-06-01T00:00:00+00:00",
        },
    )
    assert profile["posts"] == 3
    assert profile["first_post_at"] == "2024-01-01T00:00:00+00:00"
    assert profile["last_post_at"] == "2025-06-01T00:00:00+00:00"


def test_profile_stats_recomputes_when_first_post_at_is_null(dataset) -> None:
    ensure_x_datasets(dataset)
    first = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    last = first + timedelta(days=10)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            {
                "tweet_id": "1",
                "kind": "matched",
                "query_slug": "q",
                "created_at": first,
                "created_month": "2026-06",
                "author_id": "a1",
                "text": "old",
                "full_text": "old",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            },
            {
                "tweet_id": "2",
                "kind": "matched",
                "query_slug": "q",
                "created_at": last,
                "created_month": "2026-06",
                "author_id": "a1",
                "text": "new",
                "full_text": "new",
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
        AUTHOR_STATS_V1,
        [
            {
                "author_id": "a1",
                "matched_count": 2,
                "referenced_count": 0,
                "first_post_at": None,
                "last_post_at": last,
                "updated_at": last,
            }
        ],
    )
    stats = profile_stats(dataset, "a1")
    assert stats is not None
    assert stats["first_post_at"] is not None
    assert stats["last_post_at"] is not None


def _stats_post(tweet_id: str, author_id: str, created_at: datetime) -> dict:
    return {
        "tweet_id": tweet_id,
        "kind": "matched",
        "query_slug": "q",
        "created_at": created_at,
        "created_month": created_at.strftime("%Y-%m"),
        "author_id": author_id,
        "text": tweet_id,
        "full_text": tweet_id,
        "lang": "en",
        "conversation_id": "",
        "like_count": 0,
        "retweet_count": 0,
        "reply_count": 0,
        "media_urls": "",
    }

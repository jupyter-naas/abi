"""Author stats cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.author_stats import (
    count_authors_missing_first_post,
    earliest_post_at_by_author,
    merge_profile_with_stats,
    profile_stats,
    stamp_missing_first_post_at_from_posts,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHOR_STATS_V1,
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


def test_earliest_post_at_by_author_sorts_and_drops_later_tweets(dataset) -> None:
    ensure_x_datasets(dataset)
    first = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    later = first + timedelta(days=10)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            _stats_post("2", "a1", later),
            _stats_post("1", "a1", first),
            _stats_post("3", "a2", later),
        ],
    )
    by_author = earliest_post_at_by_author(dataset)
    first_a1 = by_author["a1"]
    if hasattr(first_a1, "isoformat"):
        assert first_a1.isoformat().startswith("2026-06-01")
    else:
        assert str(first_a1).startswith("2026-06-01")
    assert "a2" in by_author


def test_stamp_missing_first_post_at_from_posts(dataset) -> None:
    ensure_x_datasets(dataset)
    first = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    last = first + timedelta(days=10)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            _stats_post("1", "a1", first),
            _stats_post("2", "a1", last),
            _stats_post("3", "a2", first),
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
            },
            {
                "author_id": "a2",
                "matched_count": 1,
                "referenced_count": 0,
                "first_post_at": None,
                "last_post_at": first,
                "updated_at": first,
            },
        ],
    )
    assert count_authors_missing_first_post(dataset) == 2
    filled = stamp_missing_first_post_at_from_posts(dataset)
    assert filled == 2
    assert count_authors_missing_first_post(dataset) == 0
    rows = {
        str(row["author_id"]): row
        for row in dataset.query(
            f"SELECT author_id, first_post_at, last_post_at FROM {AUTHOR_STATS_V1}",
            namespace=X_DATASET_NAMESPACE,
        ).rows
    }
    assert rows["a1"]["first_post_at"] is not None
    assert rows["a2"]["first_post_at"] is not None
    first_a1 = rows["a1"]["first_post_at"]
    if hasattr(first_a1, "isoformat"):
        assert first_a1.isoformat().startswith("2026-06-01")
    else:
        assert str(first_a1).startswith("2026-06-01")
    assert stamp_missing_first_post_at_from_posts(dataset) == 0

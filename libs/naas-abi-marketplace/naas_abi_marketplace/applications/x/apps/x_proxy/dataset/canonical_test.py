"""Canonical projection counts (match-wins, one row per tweet)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetSchemaError,
    DatasetSpec,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset import api as ds_api
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    AUTHOR_STATS_V1,
    AUTHORS_V1,
    POSTS_V1,
    X_DATASET_NAMESPACE,
    _author_stats_v1_spec,
    _refresh_dataset_table_comment,
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


def test_graph_totals_dedupes_duplicate_author_rows(dataset) -> None:
    """Multiple authors_v1 rows per author_id must not multiply tweet counts."""
    ensure_x_datasets(dataset)
    now = datetime.now(UTC)
    seen_old = datetime(2020, 1, 1, tzinfo=UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            {
                "tweet_id": "99",
                "kind": "matched",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a1",
                "text": "t",
                "full_text": "t",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            }
        ],
    )
    author_row = {
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
    }
    upsert_table(
        dataset,
        AUTHORS_V1,
        [
            {**author_row, "seen_at": seen_old},
            {**author_row, "seen_at": now, "display_name": "Alice Latest"},
        ],
    )
    totals = ds_api.graph_totals(dataset)
    assert totals["posts"] == 1
    tweet_total, rows = ds_api.search_tweets(dataset, "", limit=10)
    assert tweet_total == 1
    assert rows[0]["display_name"] == "Alice Latest"


def test_search_users_counts_one_row_per_author_id(dataset) -> None:
    ensure_x_datasets(dataset)
    now = datetime.now(UTC)
    seen_old = datetime(2020, 1, 1, tzinfo=UTC)
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
            }
        ],
    )
    author_row = {
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
    }
    upsert_table(
        dataset,
        AUTHORS_V1,
        [
            {**author_row, "seen_at": seen_old},
            {**author_row, "seen_at": now},
        ],
    )
    total, users = ds_api.search_users(dataset, "", limit=10)
    assert total == 1
    assert len(users) == 1


def test_search_users_dedupes_username_across_author_ids(dataset) -> None:
    """Same handle with two X ``author_id`` values appears once; no stat merge."""
    ensure_x_datasets(dataset)
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            {
                "tweet_id": "30",
                "kind": "matched",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a1",
                "text": "one",
                "full_text": "one",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            },
            {
                "tweet_id": "31",
                "kind": "matched",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a2",
                "text": "two",
                "full_text": "two",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            },
        ],
    )
    author_row = {
        "display_name": "Dup",
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
    }
    upsert_table(
        dataset,
        AUTHORS_V1,
        [
            {
                **author_row,
                "author_id": "a1",
                "username": "NewsHub",
                "seen_at": now - timedelta(days=1),
            },
            {**author_row, "author_id": "a2", "username": "newshub", "seen_at": now},
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
                "first_post_at": now,
                "last_post_at": now,
                "updated_at": now,
            },
            {
                "author_id": "a2",
                "matched_count": 3,
                "referenced_count": 1,
                "first_post_at": now,
                "last_post_at": now,
                "updated_at": now,
            },
        ],
    )
    total, users = ds_api.search_users(dataset, "", limit=10)
    assert total == 1
    assert len(users) == 1
    assert users[0]["username"] in ("NewsHub", "newshub")
    assert users[0]["matched_count"] == 3
    assert users[0]["referenced_count"] == 1


def test_search_users_uses_author_stats_when_present(dataset) -> None:
    ensure_x_datasets(dataset)
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            {
                "tweet_id": "20",
                "kind": "matched",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a1",
                "text": "t",
                "full_text": "t",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            }
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
                "description": "drones",
                "location": "Paris",
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
    upsert_table(
        dataset,
        AUTHOR_STATS_V1,
        [
            {
                "author_id": "a1",
                "matched_count": 3,
                "referenced_count": 1,
                "first_post_at": now,
                "last_post_at": now,
                "updated_at": now,
            }
        ],
    )
    total, users = ds_api.search_users(dataset, "paris", limit=10)
    assert total == 1
    assert users[0]["username"] == "alice"
    assert users[0]["matched_count"] == 3
    assert "_result_total" not in users[0]


def test_user_posts_uses_cached_author_stats_total(dataset) -> None:
    ensure_x_datasets(dataset)
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            {
                "tweet_id": "10",
                "kind": "matched",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "a1",
                "text": "hello",
                "full_text": "hello",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            }
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
    upsert_table(
        dataset,
        AUTHOR_STATS_V1,
        [
            {
                "author_id": "a1",
                "matched_count": 1,
                "referenced_count": 0,
                "first_post_at": now,
                "last_post_at": now,
                "updated_at": now,
            }
        ],
    )
    profile, total, posts = ds_api.user_posts(dataset, "alice", limit=10)
    assert profile is not None
    assert total == 1
    assert len(posts) == 1
    assert posts[0]["tweet_id"] == "10"
    assert "_result_total" not in posts[0]
    assert profile["first_post_at"] is not None


def test_user_posts_backfills_null_first_post_at(dataset) -> None:
    """Stats rows from before first_post_at existed still have last_post_at."""
    ensure_x_datasets(dataset)
    first = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    last = first + timedelta(days=20)
    upsert_table(
        dataset,
        POSTS_V1,
        [_post("10", "matched", "a1", first), _post("11", "matched", "a1", last)],
    )
    upsert_table(dataset, AUTHORS_V1, [_author("a1", "alice", last)])
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
    profile, total, posts = ds_api.user_posts(dataset, "alice", limit=10)
    assert profile is not None
    assert total == 2
    assert len(posts) == 2
    assert profile["first_post_at"] is not None
    first_at = profile["first_post_at"]
    if hasattr(first_at, "isoformat"):
        first_at = first_at.isoformat()
    assert str(first_at).startswith("2026-06-01")


def test_user_posts_ignores_stale_duplicate_author_id_for_same_handle(dataset) -> None:
    """Resolve handle to the newest ``author_id``; do not inflate totals."""
    ensure_x_datasets(dataset)
    now = datetime.now(UTC)
    author_row = {
        "display_name": "Dup",
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
    }
    upsert_table(
        dataset,
        POSTS_V1,
        [
            {
                "tweet_id": "99",
                "kind": "matched",
                "query_slug": "q",
                "created_at": now,
                "created_month": "2026-09",
                "author_id": "current",
                "text": "live",
                "full_text": "live",
                "lang": "en",
                "conversation_id": "",
                "like_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "media_urls": "",
            }
        ],
    )
    upsert_table(
        dataset,
        AUTHORS_V1,
        [
            {
                **author_row,
                "author_id": "stale",
                "username": "NewsHub",
                "seen_at": now - timedelta(days=30),
            },
            {
                **author_row,
                "author_id": "current",
                "username": "newshub",
                "seen_at": now,
            },
        ],
    )
    upsert_table(
        dataset,
        AUTHOR_STATS_V1,
        [
            {
                "author_id": "stale",
                "matched_count": 1140,
                "referenced_count": 0,
                "first_post_at": now - timedelta(days=30),
                "last_post_at": now - timedelta(days=30),
                "updated_at": now,
            },
            {
                "author_id": "current",
                "matched_count": 1,
                "referenced_count": 0,
                "first_post_at": now,
                "last_post_at": now,
                "updated_at": now,
            },
        ],
    )
    profile, total, posts = ds_api.user_posts(dataset, "NewsHub", limit=10)
    assert profile is not None
    assert profile["author_id"] == "current"
    assert total == 1
    assert len(posts) == 1


def _post(tweet_id: str, kind: str, author_id: str, created_at, **extra) -> dict:
    text = extra.pop("text", f"post {tweet_id}")
    return {
        "tweet_id": tweet_id,
        "kind": kind,
        "query_slug": extra.pop("query_slug", "q"),
        "created_at": created_at,
        "created_month": created_at.strftime("%Y-%m"),
        "author_id": author_id,
        "text": text,
        "full_text": text,
        "lang": "en",
        "conversation_id": "",
        "like_count": 0,
        "retweet_count": 0,
        "reply_count": 0,
        "media_urls": extra.pop("media_urls", ""),
    }


def _author(author_id: str, username: str, seen_at, **extra) -> dict:
    return {
        "author_id": author_id,
        "username": username,
        "display_name": extra.get("display_name", username.title()),
        "description": "",
        "location": extra.get("location", ""),
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
        "seen_at": seen_at,
    }


def test_ensure_x_datasets_checks_the_catalog_once_per_dataset(dataset) -> None:
    ensure_x_datasets(dataset)
    calls = {"n": 0}
    original = dataset.create

    def counting_create(spec):
        calls["n"] += 1
        return original(spec)

    dataset.create = counting_create
    ensure_x_datasets(dataset)
    ds_api.search_users(dataset, "")
    assert calls["n"] == 0


def test_ensure_x_datasets_rewrites_stale_author_stats_spec_comment(dataset) -> None:
    """ALTER added first_post_at; a stale COMMENT left MERGE ignoring the column."""
    ensure_x_datasets(dataset)
    stale = DatasetSpec(
        name=AUTHOR_STATS_V1,
        namespace=X_DATASET_NAMESPACE,
        columns=(
            ColumnSpec(name="author_id", type="string"),
            ColumnSpec(name="matched_count", type="integer"),
            ColumnSpec(name="referenced_count", type="integer"),
            ColumnSpec(name="last_post_at", type="timestamp"),
            ColumnSpec(name="updated_at", type="timestamp"),
        ),
        primary_key=("author_id",),
    )
    stale_comment = "abi.dataset-spec:" + json.dumps(
        stale.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    escaped = stale_comment.replace("'", "''")
    dataset.query(
        f"COMMENT ON TABLE {AUTHOR_STATS_V1} IS '{escaped}'",  # nosec B608
        namespace=X_DATASET_NAMESPACE,
    )
    now = datetime.now(UTC)
    stale_row = {
        "author_id": "a1",
        "matched_count": 1,
        "referenced_count": 0,
        "first_post_at": now,
        "last_post_at": now,
        "updated_at": now,
    }
    with pytest.raises(DatasetSchemaError, match="unknown columns"):
        dataset.write(
            AUTHOR_STATS_V1,
            [stale_row],
            namespace=X_DATASET_NAMESPACE,
            mode="upsert",
        )
    dataset.flush(AUTHOR_STATS_V1, namespace=X_DATASET_NAMESPACE)
    _refresh_dataset_table_comment(dataset, _author_stats_v1_spec())
    written = upsert_table(dataset, AUTHOR_STATS_V1, [stale_row])
    assert written == 1
    stored = dataset.query(
        f"SELECT first_post_at FROM {AUTHOR_STATS_V1} WHERE author_id = 'a1'",
        namespace=X_DATASET_NAMESPACE,
    )
    assert stored.rows[0]["first_post_at"] is not None


def test_post_by_id_prefers_the_matched_row_and_carries_its_author(dataset) -> None:
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            _post("7", "referenced", "a1", now, text="as context"),
            _post("7", "matched", "a1", now, text="as match", query_slug="ai"),
        ],
    )
    upsert_table(dataset, AUTHORS_V1, [_author("a1", "alice", now, location="Paris")])
    post = ds_api.post_by_id(dataset, "7")
    assert post is not None
    assert post["kind"] == "matched"
    assert post["query_slug"] == "ai"
    assert post["username"] == "alice"
    assert post["location"] == "Paris"
    assert ds_api.post_by_id(dataset, "8") is None


def test_search_tweets_matches_author_handle_and_pages_newest_first(dataset) -> None:
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            _post("1", "matched", "a1", now - timedelta(hours=2), text="hello"),
            _post("2", "matched", "a1", now - timedelta(hours=1), text="world"),
            _post("3", "matched", "a2", now, text="unrelated"),
            # Referenced twin of a matched tweet: never a separate hit.
            _post("2", "referenced", "a1", now - timedelta(hours=1), text="world"),
        ],
    )
    upsert_table(
        dataset,
        AUTHORS_V1,
        [_author("a1", "grok", now), _author("a2", "bob", now)],
    )
    total, rows = ds_api.search_tweets(dataset, "@GROK", limit=1)
    assert total == 2
    assert [row["tweet_id"] for row in rows] == ["2"]
    assert rows[0]["kind"] == "matched"
    assert rows[0]["username"] == "grok"
    total, rows = ds_api.search_tweets(dataset, "grok", offset=1, limit=1)
    assert (total, [row["tweet_id"] for row in rows]) == (2, ["1"])
    # Past the last page the total is still reported.
    total, rows = ds_api.search_tweets(dataset, "grok", offset=5, limit=1)
    assert (total, rows) == (2, [])


def test_search_users_pages_busiest_first_with_profile_and_stats(dataset) -> None:
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        AUTHORS_V1,
        [
            _author("a1", "quiet", now, location="Lyon"),
            _author("a2", "busy", now, location="Lyon"),
        ],
    )
    upsert_table(
        dataset,
        AUTHOR_STATS_V1,
        [
            {
                "author_id": "a1",
                "matched_count": 1,
                "referenced_count": 0,
                "first_post_at": now,
                "last_post_at": now,
                "updated_at": now,
            },
            {
                "author_id": "a2",
                "matched_count": 5,
                "referenced_count": 2,
                "first_post_at": now,
                "last_post_at": now,
                "updated_at": now,
            },
        ],
    )
    total, users = ds_api.search_users(dataset, "lyon", limit=1)
    assert total == 2
    assert [user["username"] for user in users] == ["busy"]
    assert users[0]["referenced_count"] == 2
    assert users[0]["display_name"] == "Busy"
    total, users = ds_api.search_users(dataset, "lyon", offset=1, limit=1)
    assert (total, [user["username"] for user in users]) == (2, ["quiet"])


def test_user_posts_kind_filter_applies_after_match_wins(dataset) -> None:
    now = datetime.now(UTC)
    upsert_table(
        dataset,
        POSTS_V1,
        [
            _post("1", "matched", "a1", now),
            _post("1", "referenced", "a1", now),
            _post("2", "referenced", "a1", now - timedelta(hours=1)),
        ],
    )
    upsert_table(dataset, AUTHORS_V1, [_author("a1", "alice", now)])
    _, total, posts = ds_api.user_posts(dataset, "alice", kind="referenced")
    assert total == 1
    assert [post["tweet_id"] for post in posts] == ["2"]
    _, total, posts = ds_api.user_posts(dataset, "ALICE")
    assert total == 2
    assert [post["tweet_id"] for post in posts] == ["1", "2"]
    assert posts[0]["kind"] == "matched"
    assert ds_api.user_posts(dataset, "nobody") == (None, 0, [])

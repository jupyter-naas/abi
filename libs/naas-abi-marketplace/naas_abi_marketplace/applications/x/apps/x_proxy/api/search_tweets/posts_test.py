"""Unit tests for the Search Tweets dataset publisher."""

import json

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_TWEET_LIMIT,
    SnapshotContext,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.search_tweets import posts


class _FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[f"{prefix}/{key}"] = content

    def get_object(self, prefix: str, key: str) -> bytes:
        path = f"{prefix}/{key}"
        if path not in self.objects:
            raise FileNotFoundError(path)
        return self.objects[path]


class _RecordingContext(SnapshotContext):
    def __init__(
        self,
        storage: _FakeObjectStorage,
        tweet_rows: list[dict],
        graph_state: dict[str, str] | None = None,
    ) -> None:
        super().__init__(storage, None, queries=[])  # type: ignore[arg-type]
        self._tweet_rows = tweet_rows
        self._graph_state = graph_state

    def tweet_graph_state(self) -> dict[str, str]:
        return dict(self._graph_state or {})

    def all_tweets_for_search(self) -> list[dict]:
        return list(self._tweet_rows)


def _post(tweet_id: str, created: str, **extra) -> dict:
    return {
        "tweet_id": tweet_id,
        "created_at": created,
        "text": f"post {tweet_id}",
        "username": "alice",
        "location": "",
        "verified_type": "",
        "referenced": False,
        "media_count": 0,
        "queries": ["drone"],
        **extra,
    }


def _manifest(storage: _FakeObjectStorage) -> dict:
    return json.loads(storage.objects["x/apps/x_proxy/search_tweets/manifest.json"])


def _index(storage: _FakeObjectStorage) -> dict:
    return json.loads(storage.objects["x/apps/x_proxy/search_tweets/posts.json"])


def _preview(storage: _FakeObjectStorage) -> dict:
    return json.loads(
        storage.objects["x/apps/x_proxy/search_tweets/posts_preview.json"]
    )


def test_publish_writes_full_index_and_preview():
    storage = _FakeObjectStorage()
    rows = [_post(str(i), f"2026-07-07T{12 + i % 10:02d}:00:00+00:00") for i in range(5)]
    summary = posts.publish(_RecordingContext(storage, rows))

    assert summary["posts"] == 5
    assert summary["preview"] == 5
    assert _index(storage)["count"] == 5
    assert len(_preview(storage)["posts"]) == 5
    assert _manifest(storage)["index_columns"] == posts.INDEX_COLUMNS


def test_preview_is_capped_at_default_tweet_limit():
    storage = _FakeObjectStorage()
    rows = [_post(str(i), f"2026-07-07T12:00:{i % 60:02d}+00:00") for i in range(1200)]
    posts.publish(_RecordingContext(storage, rows))

    assert _index(storage)["count"] == 1200
    assert len(_preview(storage)["posts"]) == DEFAULT_TWEET_LIMIT


def test_unchanged_source_skips_rebuild():
    storage = _FakeObjectStorage()
    state = {"watermark": "2026-07-07T12:00:00+00:00"}
    posts.publish(_RecordingContext(storage, [_post("1", "2026-07-07T12:00:00+00:00")], state))
    written = dict(storage.objects)

    summary = posts.publish(
        _RecordingContext(storage, [_post("2", "2026-07-07T13:00:00+00:00")], state)
    )

    assert summary["skipped"] is True
    assert storage.objects == written

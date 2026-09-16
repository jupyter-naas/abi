"""Tests for direct X Proxy artifacts and persisted media."""

import json

from naas_abi_marketplace.applications.x.apps.x_proxy.api import artifacts


class _Storage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[f"{prefix}/{key}"] = content

    def get_object(self, prefix: str, key: str) -> bytes:
        return self.objects[f"{prefix}/{key}"]


def _post(**extra):
    return {
        "created_at": "2026-09-11T12:00:00+00:00",
        "text": "hello",
        "url": "https://x.com/alice/status/123",
        "username": "alice",
        **extra,
    }


def test_post_artifact_is_idempotent_without_media():
    storage = _Storage()
    first = artifacts.publish_post(storage, _post())
    second = artifacts.publish_post(storage, _post())

    assert first["skipped"] is False
    assert second["skipped"] is True
    doc = json.loads(storage.objects["x/apps/x_proxy/posts/by-id/123/post.json"])
    assert doc["post"]["text"] == "hello"
    assert doc["media_complete"] is True


def test_user_artifact_points_at_direct_localized_post():
    storage = _Storage()
    artifacts.publish_user(
        storage,
        "Alice",
        {"profile": {"username": "Alice"}, "posts": [_post()]},
    )

    doc = json.loads(storage.objects["x/apps/x_proxy/users/by-handle/alice/user.json"])
    assert doc["bundle"]["posts"][0]["url"].endswith("/status/123")
    assert "x/apps/x_proxy/posts/by-id/123/post.json" in storage.objects


def test_unapproved_media_host_is_never_downloaded():
    storage = _Storage()
    result = artifacts.publish_post(
        storage, _post(media_url="https://example.com/tracker.png")
    )

    assert result["media_complete"] is False
    doc = json.loads(storage.objects["x/apps/x_proxy/posts/by-id/123/post.json"])
    assert "media_url" not in doc["post"]
    assert doc["post"]["source_media_urls"] == ["https://example.com/tracker.png"]


def test_approved_media_is_persisted_and_referenced_locally(monkeypatch):
    class _Response:
        headers = {"Content-Type": "image/png"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def geturl(self):
            return "https://pbs.twimg.com/media/example.png"

        def read(self, _size):
            if getattr(self, "read_once", False):
                return b""
            self.read_once = True
            return b"image-bytes"

    monkeypatch.setattr(artifacts, "urlopen", lambda *_args, **_kwargs: _Response())
    storage = _Storage()
    result = artifacts.publish_post(
        storage,
        _post(media_url="https://pbs.twimg.com/media/example.png"),
    )

    assert result["media_complete"] is True
    doc = json.loads(storage.objects["x/apps/x_proxy/posts/by-id/123/post.json"])
    local = doc["post"]["media_url"]
    assert local.startswith("posts/by-id/123/media/")
    assert f"x/apps/x_proxy/{local}" in storage.objects


def test_unsafe_artifact_identifiers_are_rejected():
    storage = _Storage()
    try:
        artifacts.publish_user(storage, "../alice", {"profile": {}, "posts": []})
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe username accepted")

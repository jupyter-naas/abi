"""Unit tests for the incremental Users dataset publisher."""

import json

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    user_shard,
)
from naas_abi_marketplace.applications.x.apps.x.api.search_users import users


class _FakeObjectStorage:
    """In-memory object storage exposing the two methods SnapshotContext uses."""

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
    """SnapshotContext with the three graph reads stubbed and recorded.

    Storage stays real (against :class:`_FakeObjectStorage`) so the manifest
    round-trip that drives the incremental decision is genuinely exercised.
    """

    def __init__(self, storage: _FakeObjectStorage, authors: list[dict]) -> None:
        super().__init__(storage, None, queries=[])  # type: ignore[arg-type]
        self._authors = authors
        self.posts_queried: list[list[str]] = []

    def all_authors(self) -> list[dict]:
        return list(self._authors)

    def accounts_for_usernames(self, usernames: list[str]) -> dict[str, dict]:
        return {u: {"author_id": f"id-{u}"} for u in usernames}

    def posts_for_usernames(self, usernames: list[str]) -> dict[str, list[dict]]:
        self.posts_queried.append(list(usernames))
        return {
            u: [{"created_at": "2026-07-07T12:00:00+00:00", "text": f"post by {u}"}]
            for u in usernames
        }


def _author(username: str, posts: int, last: str) -> dict:
    return {
        "username": username,
        "posts": posts,
        "last_post_at": last,
        "location": "",
        "verified_type": "",
    }


_A = _author("alice", 2, "2026-07-07T12:00:00+00:00")
_B = _author("bob", 1, "2026-07-07T11:00:00+00:00")


def _manifest(storage: _FakeObjectStorage) -> dict:
    return json.loads(storage.objects["x/apps/x/search_users/shards.json"])


def test_first_publish_builds_every_shard():
    storage = _FakeObjectStorage()
    ctx = _RecordingContext(storage, [_A, _B])

    summary = users.publish(ctx)

    assert summary["users"] == 2
    assert summary["shards_rebuilt"] == len({user_shard("alice"), user_shard("bob")})
    assert summary["shards_written"] == summary["shards_rebuilt"]
    # No manifest to compare against → both authors' posts are fetched.
    assert sorted(ctx.posts_queried[0]) == ["alice", "bob"]
    assert all(e.get("fingerprint") for e in _manifest(storage)["shards"].values())


def test_republish_with_no_change_queries_nothing_and_writes_nothing():
    """The whole point: an unchanged shard costs no SPARQL and no upload."""
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B]))
    written_before = dict(storage.objects)

    ctx = _RecordingContext(storage, [_A, _B])
    summary = users.publish(ctx)

    assert summary["shards_rebuilt"] == 0
    assert summary["shards_written"] == 0
    assert ctx.posts_queried == []
    # Post files untouched; only the index + manifest are rewritten.
    for path, payload in written_before.items():
        if "/posts/" in path:
            assert storage.objects[path] == payload
    # Carried-forward entries keep their per-shard totals.
    assert summary["posts"] == 2


def test_only_the_changed_authors_shard_is_requeried():
    # Precondition: the two authors must live in different shards for "only one
    # shard was requeried" to mean anything (sha1 of the name — deterministic).
    assert user_shard("alice") != user_shard("bob")

    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B]))

    moved = _author("alice", 3, "2026-07-07T13:00:00+00:00")
    ctx = _RecordingContext(storage, [moved, _B])
    summary = users.publish(ctx)

    assert summary["shards_rebuilt"] == 1
    assert ctx.posts_queried == [["alice"]]
    # bob's shard entry survived untouched.
    entry = _manifest(storage)["shards"][user_shard("bob")]
    assert entry["authors"] == 1


def test_full_forces_a_complete_rebuild():
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B]))

    ctx = _RecordingContext(storage, [_A, _B])
    summary = users.publish(ctx, full=True)

    assert summary["shards_rebuilt"] == len(_manifest(storage)["shards"])
    assert sorted(ctx.posts_queried[0]) == ["alice", "bob"]
    # Rebuilt but byte-identical → still not re-uploaded.
    assert summary["shards_written"] == 0


def test_manifest_without_fingerprints_triggers_one_full_rebuild():
    """A manifest from before this was incremental must not be trusted."""
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B]))
    stale = _manifest(storage)
    for entry in stale["shards"].values():
        entry.pop("fingerprint")
    storage.objects["x/apps/x/search_users/shards.json"] = json.dumps(stale).encode()

    ctx = _RecordingContext(storage, [_A, _B])
    summary = users.publish(ctx)

    assert summary["shards_rebuilt"] == len(stale["shards"])
    assert sorted(ctx.posts_queried[0]) == ["alice", "bob"]


def test_no_authors_writes_an_empty_manifest():
    storage = _FakeObjectStorage()
    ctx = _RecordingContext(storage, [])

    summary = users.publish(ctx)

    assert summary == {
        "users": 0,
        "posts": 0,
        "shards_rebuilt": 0,
        "shards_written": 0,
        "shards_unchanged": 0,
    }
    assert _manifest(storage)["shards"] == {}
    assert ctx.posts_queried == []

"""Unit tests for the incremental Users dataset publisher."""

import json

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    SnapshotContext,
    user_shard,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.search_users import users


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

    def __init__(
        self,
        storage: _FakeObjectStorage,
        authors: list[dict],
        descriptions: dict[str, str] | None = None,
        display_names: dict[str, str] | None = None,
        graph_state: dict[str, str] | None = None,
    ) -> None:
        super().__init__(storage, None, queries=[])  # type: ignore[arg-type]
        self._authors = authors
        self._descriptions = descriptions or {}
        self._display_names = display_names or {}
        self._graph_state = graph_state
        self.posts_queried: list[list[str]] = []
        self.authors_queried = 0

    def tweet_graph_state(self) -> dict[str, str]:
        """Empty by default, which disables the skip gate.

        Most tests here exercise the per-shard incremental logic, which only runs
        once the gate has let the publish through; they pass no state so it
        always does. The gate itself is covered by the tests that do pass one.
        """
        return dict(self._graph_state or {})

    def all_authors(self) -> list[dict]:
        self.authors_queried += 1
        return list(self._authors)

    def all_descriptions(self) -> dict[str, str]:
        return dict(self._descriptions)

    def all_display_names(self) -> dict[str, str]:
        return dict(self._display_names)

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
    return json.loads(storage.objects["x/apps/x_proxy/search_users/shards.json"])


def _index(storage: _FakeObjectStorage) -> dict:
    return json.loads(storage.objects["x/apps/x_proxy/search_users/users.json"])


def _col(index: dict, row: list, name: str):
    return row[index["columns"].index(name)]


def test_index_carries_the_bio_and_display_name_as_trailing_columns():
    """Search results render the name as the title and the bio as the snippet."""
    storage = _FakeObjectStorage()
    users.publish(
        _RecordingContext(
            storage,
            [_A, _B],
            {"alice": "Builds things."},
            {"alice": "Alice Example"},
        )
    )

    index = _index(storage)
    assert index["columns"][-2:] == ["description", "display_name"]
    rows = {row[0]: row for row in index["users"]}
    assert _col(index, rows["alice"], "description") == "Builds things."
    assert _col(index, rows["alice"], "display_name") == "Alice Example"
    # An author with no bio / name still has the columns, empty.
    assert _col(index, rows["bob"], "description") == ""
    assert _col(index, rows["bob"], "display_name") == ""


def test_long_bios_are_truncated():
    storage = _FakeObjectStorage()
    long_bio = "x" * (users.MAX_DESCRIPTION_CHARS + 50)
    users.publish(_RecordingContext(storage, [_A], {"alice": long_bio}))

    index = _index(storage)
    published = _col(index, index["users"][0], "description")
    assert len(published) == users.MAX_DESCRIPTION_CHARS
    assert published.endswith("…")


def test_a_bio_change_alone_does_not_rebuild_shards():
    """Bios live in the index, so they must not invalidate the post files."""
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B]))

    ctx = _RecordingContext(storage, [_A, _B], {"alice": "New bio."})
    summary = users.publish(ctx)

    assert ctx.posts_queried == []
    assert summary["shards_written"] == 0
    index = _index(storage)
    assert _col(index, index["users"][0], "description") == "New bio."


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
    storage.objects["x/apps/x_proxy/search_users/shards.json"] = json.dumps(
        stale
    ).encode()

    ctx = _RecordingContext(storage, [_A, _B])
    summary = users.publish(ctx)

    assert summary["shards_rebuilt"] == len(stale["shards"])
    assert sorted(ctx.posts_queried[0]) == ["alice", "bob"]


_STATE = {"tweets": "3", "newest": "2026-07-07T12:00:00+00:00"}


def test_an_unchanged_tweet_graph_skips_the_rebuild_entirely():
    """The expensive pair never runs, and nothing published is touched."""
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B], graph_state=_STATE))
    written_before = dict(storage.objects)

    ctx = _RecordingContext(storage, [_A, _B], graph_state=_STATE)
    summary = users.publish(ctx)

    assert summary["skipped"] is True
    assert summary["users"] == 2
    assert summary["posts"] == 2
    # Neither full-graph aggregate was issued.
    assert ctx.authors_queried == 0
    assert ctx.posts_queried == []
    # Every published byte survived, including the manifest's timestamp.
    assert storage.objects == written_before


def test_an_index_column_change_rewrites_users_without_touching_shards():
    """Trailing index columns must land without a 256-shard rebuild."""
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B], graph_state=_STATE))
    stale = _manifest(storage)
    stale.pop("index_columns")
    storage.objects["x/apps/x_proxy/search_users/shards.json"] = json.dumps(
        stale
    ).encode()

    ctx = _RecordingContext(
        storage,
        [_A, _B],
        display_names={"alice": "Alice Example"},
        graph_state=_STATE,
    )
    summary = users.publish(ctx)

    assert summary.get("skipped") is None
    assert ctx.posts_queried == []
    assert summary["shards_rebuilt"] == 0
    index = _index(storage)
    rows = {row[0]: row for row in index["users"]}
    assert _col(index, rows["alice"], "display_name") == "Alice Example"


def test_new_posts_reopen_the_rebuild():
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B], graph_state=_STATE))

    moved = _author("alice", 3, "2026-07-07T13:00:00+00:00")
    ctx = _RecordingContext(
        storage,
        [moved, _B],
        graph_state={"tweets": "4", "newest": "2026-07-07T13:00:00+00:00"},
    )
    summary = users.publish(ctx)

    assert summary.get("skipped") is None
    assert ctx.authors_queried == 1
    assert summary["shards_rebuilt"] == 1
    assert ctx.posts_queried == [["alice"]]


def test_a_backfill_of_older_posts_reopens_the_rebuild():
    """The newest timestamp does not move, but the total does."""
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B], graph_state=_STATE))

    ctx = _RecordingContext(
        storage,
        [_author("alice", 5, "2026-07-07T12:00:00+00:00"), _B],
        graph_state={"tweets": "6", "newest": _STATE["newest"]},
    )
    summary = users.publish(ctx)

    assert summary.get("skipped") is None
    assert ctx.authors_queried == 1


def test_full_bypasses_the_unchanged_graph_gate():
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B], graph_state=_STATE))

    ctx = _RecordingContext(storage, [_A, _B], graph_state=_STATE)
    summary = users.publish(ctx, full=True)

    assert summary.get("skipped") is None
    assert ctx.authors_queried == 1
    assert sorted(ctx.posts_queried[0]) == ["alice", "bob"]


def test_a_probe_that_returned_nothing_never_skips():
    """No signal is not the same as no change — rebuild rather than guess."""
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B]))

    ctx = _RecordingContext(storage, [_A, _B])
    summary = users.publish(ctx)

    assert summary.get("skipped") is None
    assert ctx.authors_queried == 1


def test_an_unchanged_index_is_not_re_uploaded():
    storage = _FakeObjectStorage()
    users.publish(_RecordingContext(storage, [_A, _B]))
    index_before = storage.objects["x/apps/x_proxy/search_users/users.json"]

    # A different built_at would rewrite users.json if the digest covered it.
    ctx = _RecordingContext(storage, [_A, _B])
    ctx.built_at = ctx.built_at.replace(year=2027)
    summary = users.publish(ctx)

    assert summary["index_written"] is False
    assert storage.objects["x/apps/x_proxy/search_users/users.json"] == index_before


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

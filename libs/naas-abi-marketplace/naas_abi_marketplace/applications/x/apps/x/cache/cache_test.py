"""Unit tests for the X Parquet projection.

The projection is a second reading of the same envelopes the graph is built from,
so the tests that matter are the ones pinning it to the pipeline's semantics —
what counts as a match, what counts as context — and the ones proving a refresh
costs only the new envelopes.
"""

import json

from naas_abi_marketplace.applications.x.apps.x.cache import projection
from naas_abi_marketplace.applications.x.apps.x.cache.envelopes import (
    envelope_timestamp,
    parse_envelope,
)
from naas_abi_marketplace.applications.x.apps.x.cache.reader import (
    CacheReader,
    _months_between,
)
from naas_abi_marketplace.applications.x.apps.x.cache.schema import ENVELOPE_PREFIX
from naas_abi_marketplace.applications.x.apps.x.cache.storage import walk


class _Storage:
    """In-memory object storage with the directory-listing semantics of the real one.

    ``list_objects`` deliberately returns one level only, with nested prefixes
    marked by a trailing slash — the behaviour that broke the first draft of the
    projection, so the tests must reproduce it rather than a flat listing.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts = 0
        self.gets = 0

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[f"{prefix}/{key}"] = content
        self.puts += 1

    def get_object(self, prefix: str, key: str) -> bytes:
        path = f"{prefix}/{key}"
        if path not in self.objects:
            raise FileNotFoundError(path)
        self.gets += 1
        return self.objects[path]

    def delete_object(self, prefix: str, key: str) -> None:
        self.objects.pop(f"{prefix}/{key}", None)

    def list_objects(self, prefix: str = "", queue=None) -> list[str]:
        base = prefix.rstrip("/")
        head = f"{base}/" if base else ""
        entries: set[str] = set()
        for key in self.objects:
            if not key.startswith(head):
                continue
            rest = key[len(head) :]
            if "/" in rest:
                entries.add(f"{head}{rest.split('/', 1)[0]}/")
            else:
                entries.add(key)
        return sorted(entries)


class _KV:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def get(self, key: str) -> bytes:
        return self.store.get(key, b"")

    def set(self, key: str, value: bytes, ttl=None) -> None:
        self.store[key] = value


def _tweet(tweet_id: str, created: str, author: str = "a1", **extra) -> dict:
    return {
        "id": tweet_id,
        "created_at": created,
        "author_id": author,
        "text": f"post {tweet_id}",
        "lang": "en",
        **extra,
    }


def _envelope(
    matched: list[dict],
    referenced: list[dict] | None = None,
    users=None,
    ended="2026-08-12T06:00:00+00:00",
    query="(drone OR drones) lang:en",
) -> dict:
    return {
        "query": query,
        "started_at": ended,
        "ended_at": ended,
        "results": {
            "data": matched,
            "includes": {
                "tweets": referenced or [],
                "users": users or [],
                "media": [],
            },
        },
    }


def _store_envelope(storage: _Storage, name: str, doc: dict) -> None:
    storage.put_object(
        f"{ENVELOPE_PREFIX}/drones", name, json.dumps(doc).encode("utf-8")
    )


# --------------------------------------------------------------------------
# Envelope key timestamps
# --------------------------------------------------------------------------


def test_both_envelope_key_spellings_parse():
    """The archive holds two eras of naming; the watermark must read both."""
    old = envelope_timestamp(
        "x/search_recent_tweets/q/2026-06-29T17_58_45.974146+00_00_q.json"
    )
    new = envelope_timestamp(
        "x/search_recent_tweets/q/2026-08-12T05:55:16.152505+00:00_q.json"
    )
    assert old is not None and new is not None
    assert old.isoformat() == "2026-06-29T17:58:45.974146+00:00"
    assert new.isoformat() == "2026-08-12T05:55:16.152505+00:00"
    assert old < new


def test_an_unreadable_key_yields_none_so_it_is_not_skipped():
    assert envelope_timestamp("x/search_recent_tweets/q/no-timestamp-here.json") is None


# --------------------------------------------------------------------------
# Envelope parsing
# --------------------------------------------------------------------------


def test_a_post_that_matched_is_not_also_emitted_as_context():
    """``includes.tweets`` is a superset of ``data`` — the overlap is not context."""
    posts, _ = parse_envelope(
        _envelope(
            matched=[_tweet("1", "2026-08-12T05:00:00.000Z")],
            referenced=[
                _tweet("1", "2026-08-12T05:00:00.000Z"),
                _tweet("2", "2026-08-01T05:00:00.000Z"),
            ],
        )
    )
    kinds = {p["tweet_id"]: p["kind"] for p in posts}
    assert kinds == {"1": "matched", "2": "referenced"}


def test_media_urls_fall_back_to_the_preview_when_there_is_no_playable_url():
    doc = _envelope(
        matched=[
            _tweet(
                "1",
                "2026-08-12T05:00:00.000Z",
                attachments={"media_keys": ["k1", "k2"]},
            )
        ]
    )
    doc["results"]["includes"]["media"] = [
        {"media_key": "k1", "url": "https://img/photo.jpg"},
        {"media_key": "k2", "preview_image_url": "https://img/still.jpg"},
    ]
    posts, _ = parse_envelope(doc)
    assert posts[0]["media_urls"] == "https://img/photo.jpg https://img/still.jpg"


def test_authors_carry_the_observation_time_so_the_newest_wins():
    _, authors = parse_envelope(
        _envelope(
            matched=[],
            users=[
                {
                    "id": "a1",
                    "username": "alice",
                    "public_metrics": {"followers_count": 5},
                }
            ],
            ended="2026-08-12T06:00:00+00:00",
        )
    )
    assert authors[0]["seen_at"] == "2026-08-12T06:00:00+00:00"
    assert authors[0]["followers_count"] == 5


# --------------------------------------------------------------------------
# Recursive listing
# --------------------------------------------------------------------------


def test_walk_descends_into_nested_prefixes():
    storage = _Storage()
    storage.put_object("x/cache/posts/ym=2026-08", "part-1.parquet", b"a")
    storage.put_object("x/cache/posts/ym=2026-07", "part-1.parquet", b"b")
    storage.put_object("x/cache/posts", ".nexus_folder", b"")

    found = walk(storage, "x/cache/posts", suffix=".parquet")  # type: ignore[arg-type]

    assert sorted(found) == [
        "x/cache/posts/ym=2026-07/part-1.parquet",
        "x/cache/posts/ym=2026-08/part-1.parquet",
    ]
    # A single-level listing would only have seen the two directory markers.
    assert storage.list_objects("x/cache/posts") == [
        "x/cache/posts/.nexus_folder",
        "x/cache/posts/ym=2026-07/",
        "x/cache/posts/ym=2026-08/",
    ]


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------


def test_refresh_projects_then_skips_when_nothing_is_new():
    storage, kv = _Storage(), _KV()
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(matched=[_tweet("1", "2026-08-12T05:00:00.000Z")]),
    )

    first = projection.refresh(storage, kv)  # type: ignore[arg-type]
    assert first["envelopes_new"] == 1
    assert first["posts_added"] == 1

    storage.puts = 0
    second = projection.refresh(storage, kv)  # type: ignore[arg-type]

    assert second == {"skipped": True, "envelopes_total": 1, "envelopes_new": 0}
    assert storage.puts == 0


def test_only_envelopes_past_the_watermark_are_read():
    storage, kv = _Storage(), _KV()
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(matched=[_tweet("1", "2026-08-12T05:00:00.000Z")]),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]

    _store_envelope(
        storage,
        "2026-08-12T06:00:00+00:00_q.json",
        _envelope(matched=[_tweet("2", "2026-08-12T06:00:00.000Z")]),
    )
    second = projection.refresh(storage, kv)  # type: ignore[arg-type]

    assert second["envelopes_total"] == 2
    # The already-projected envelope was not re-read.
    assert second["envelopes_new"] == 1
    assert second["posts_added"] == 1
    assert second["full_rebuild"] is False


def test_an_incremental_run_appends_rather_than_replacing_the_month():
    """Overwriting the partition would delete the history already projected."""
    storage, kv = _Storage(), _KV()
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(matched=[_tweet("1", "2026-08-12T05:00:00.000Z")]),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]
    _store_envelope(
        storage,
        "2026-08-12T06:00:00+00:00_q.json",
        _envelope(matched=[_tweet("2", "2026-08-12T06:00:00.000Z")]),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]

    reader = CacheReader(storage)  # type: ignore[arg-type]
    ids = set(reader.posts().get_column("tweet_id").to_list())
    assert ids == {"1", "2"}
    assert len(walk(storage, "x/cache/posts", suffix=".parquet")) == 2  # type: ignore[arg-type]


def test_a_post_carried_by_two_refreshes_is_read_once():
    """The dedupe key spans part files, not just one refresh batch.

    An incremental run appends a part rather than rewriting the month, so a post
    that appears in envelopes either side of a watermark is written twice. Left
    uncollapsed it double-counts every windowed total and lists the post twice in
    the Users dataset. The later observation wins, carrying the newer metrics.
    """
    storage, kv = _Storage(), _KV()
    users = [{"id": "a1", "username": "alice"}]
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(
            matched=[
                _tweet(
                    "1", "2026-08-12T05:00:00.000Z", public_metrics={"like_count": 3}
                )
            ],
            users=users,
        ),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]
    _store_envelope(
        storage,
        "2026-08-12T06:00:00+00:00_q.json",
        _envelope(
            matched=[
                _tweet(
                    "1", "2026-08-12T05:00:00.000Z", public_metrics={"like_count": 9}
                )
            ],
            users=users,
        ),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]

    # Both parts are on disk — this is a read-side collapse, not a lost write.
    assert len(walk(storage, "x/cache/posts", suffix=".parquet")) == 2  # type: ignore[arg-type]

    reader = CacheReader(storage)  # type: ignore[arg-type]
    posts = reader.posts()
    assert posts.height == 1
    assert posts.row(0, named=True)["like_count"] == 9

    window = ("2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00")
    assert reader.count_in_window(*window) == 1
    assert len(reader.newest_posts(*window)) == 1
    assert len(reader.posts_by_username(["alice"])["alice"]) == 1


def test_a_schema_bump_forces_a_full_rebuild(monkeypatch):
    storage, kv = _Storage(), _KV()
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(matched=[_tweet("1", "2026-08-12T05:00:00.000Z")]),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]

    monkeypatch.setattr(projection, "SCHEMA_VERSION", 99)
    again = projection.refresh(storage, kv)  # type: ignore[arg-type]

    assert again["full_rebuild"] is True
    assert again["envelopes_new"] == 1


# --------------------------------------------------------------------------
# Reader
# --------------------------------------------------------------------------


def test_month_selection_covers_the_window_edges():
    from datetime import UTC, datetime

    months = _months_between(
        datetime(2026, 6, 28, tzinfo=UTC), datetime(2026, 8, 2, tzinfo=UTC)
    )
    assert months == ["2026-06", "2026-07", "2026-08"]


def _seeded_reader() -> CacheReader:
    storage, kv = _Storage(), _KV()
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(
            matched=[
                _tweet("1", "2026-08-12T05:00:00.000Z", author="a1"),
                _tweet("2", "2026-08-12T04:00:00.000Z", author="a2"),
            ],
            referenced=[_tweet("9", "2026-08-12T03:00:00.000Z", author="a2")],
            users=[
                {
                    "id": "a1",
                    "username": "alice",
                    "location": "USA ",
                    "description": "hi",
                },
                {"id": "a2", "username": "bob", "location": " USA"},
            ],
        ),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]
    return CacheReader(storage)  # type: ignore[arg-type]


def test_window_counts_split_matched_from_referenced():
    reader = _seeded_reader()
    start, end = "2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00"
    assert reader.count_in_window(start, end) == 2
    assert reader.count_in_window(start, end, referenced=True) == 1


def test_a_post_matched_in_a_later_tick_stops_counting_as_context():
    """Match typing wins globally, not just inside one envelope."""
    storage, kv = _Storage(), _KV()
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(matched=[], referenced=[_tweet("7", "2026-08-12T04:00:00.000Z")]),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]
    assert (
        CacheReader(storage).count_in_window(  # type: ignore[arg-type]
            "2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00", referenced=True
        )
        == 1
    )

    _store_envelope(
        storage,
        "2026-08-12T06:00:00+00:00_q.json",
        _envelope(matched=[_tweet("7", "2026-08-12T04:00:00.000Z")]),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]

    reader = CacheReader(storage)  # type: ignore[arg-type]
    start, end = "2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00"
    assert reader.count_in_window(start, end) == 1
    assert reader.count_in_window(start, end, referenced=True) == 0


def test_facet_values_merge_whitespace_variants():
    """``user_location`` really does hold both "USA " and " USA"."""
    reader = _seeded_reader()
    values = reader.facet_values(
        "2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00", "location"
    )
    assert values == [{"value": "USA", "count": 2}]


def test_newest_posts_are_ordered_and_carry_a_resolvable_url():
    reader = _seeded_reader()
    rows = reader.newest_posts(
        "2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00", limit=10
    )
    assert [r["username"] for r in rows] == ["alice", "bob"]
    assert rows[0]["url"] == "https://x.com/alice/status/1"


def test_author_index_counts_matched_and_referenced_posts():
    reader = _seeded_reader()
    index = {row["username"]: row for row in reader.author_index()}
    assert set(index) == {"alice", "bob"}
    # bob authored one match and one referenced post; both count.
    assert index["alice"]["posts"] == 1
    assert index["bob"]["posts"] == 2
    assert reader.descriptions() == {"alice": "hi"}


def test_posts_by_username_includes_referenced_context():
    """The author page is a full view: matches plus quote/reply/retweet originals."""
    reader = _seeded_reader()
    bob = reader.posts_by_username(["bob"])["bob"]
    assert [p["url"].rsplit("/", 1)[-1] for p in bob] == ["2", "9"]
    by_id = {p["url"].rsplit("/", 1)[-1]: p for p in bob}
    assert "referenced" not in by_id["2"]
    assert by_id["9"]["referenced"] is True


def test_reads_are_scoped_to_one_query():
    """Two followed queries share the projection; a per-query snapshot must not
    report the other one's posts."""
    storage, kv = _Storage(), _KV()
    users = [{"id": "a1", "username": "alice", "location": "USA"}]
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_drones.json",
        _envelope(
            matched=[
                _tweet("1", "2026-08-12T05:00:00.000Z"),
                _tweet("2", "2026-08-12T04:00:00.000Z"),
            ],
            users=users,
        ),
    )
    _store_envelope(
        storage,
        "2026-08-12T05:30:00+00:00_ships.json",
        _envelope(
            matched=[_tweet("3", "2026-08-12T04:30:00.000Z")],
            users=users,
            query="ships lang:en",
        ),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]

    reader = CacheReader(storage)  # type: ignore[arg-type]
    window = ("2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00")
    assert reader.known_query_slugs() == {"drone_or_drones_lang_en", "ships_lang_en"}
    assert reader.count_in_window(*window, query_slug="drone_or_drones_lang_en") == 2
    assert reader.count_in_window(*window, query_slug="ships_lang_en") == 1
    # Unscoped still spans both — the Users dataset wants every followed query.
    assert reader.count_in_window(*window) == 3
    assert reader.facet_values(*window, "location", query_slug="ships_lang_en") == [
        {"value": "USA", "count": 1}
    ]
    assert [
        r["url"].rsplit("/", 1)[-1]
        for r in reader.newest_posts(*window, query_slug="ships_lang_en")
    ] == ["3"]


def test_a_long_post_is_projected_untruncated():
    """X cuts ``text`` off and puts the whole post in ``note_tweet.text``."""
    storage, kv = _Storage(), _KV()
    long_post = "a very long post " * 20
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(
            matched=[
                _tweet(
                    "1",
                    "2026-08-12T05:00:00.000Z",
                    text="a very long post a very lo…",
                    note_tweet={"text": long_post},
                )
            ],
            users=[{"id": "a1", "username": "alice"}],
        ),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]

    reader = CacheReader(storage)  # type: ignore[arg-type]
    window = ("2026-08-12T00:00:00+00:00", "2026-08-13T00:00:00+00:00")
    assert reader.newest_posts(*window)[0]["text"] == long_post
    assert reader.posts_by_username(["alice"])["alice"][0]["text"] == long_post


def test_a_projection_from_an_older_schema_is_not_attached(monkeypatch):
    """Its parts lack columns this reader selects by name — fall back, don't crash."""
    from naas_abi_marketplace.applications.x.apps.x.api.publish import _attach_cache

    storage, kv = _Storage(), _KV()
    _store_envelope(
        storage,
        "2026-08-12T05:00:00+00:00_q.json",
        _envelope(matched=[_tweet("1", "2026-08-12T05:00:00.000Z")]),
    )
    projection.refresh(storage, kv)  # type: ignore[arg-type]
    assert _attach_cache(storage) is not None  # type: ignore[arg-type]

    # The same projection, now read by a build that moved the schema on.
    import naas_abi_marketplace.applications.x.apps.x.cache.schema as schema_module

    monkeypatch.setattr(schema_module, "SCHEMA_VERSION", 99)
    assert _attach_cache(storage) is None  # type: ignore[arg-type]

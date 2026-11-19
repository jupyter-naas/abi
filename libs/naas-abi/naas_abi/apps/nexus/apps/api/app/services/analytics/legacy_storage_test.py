"""The removed analytics app's object-storage files: read as data, deleted once replayed,
the others set aside."""

from __future__ import annotations

import json
import pickle

import pytest
from naas_abi.apps.nexus.apps.api.app.services.analytics.legacy_storage import (
    EVENTS_PREFIX,
    LEGACY_FILES,
    OUTPUT_DIR,
    UNREADABLE_PREFIX,
    LegacyAnalyticsStorage,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions

CALLS: list[str] = []


def _record(value: str) -> str:
    CALLS.append(value)
    return value


class _Runs:
    """Unpickling it calls ``_record``."""

    def __reduce__(self):
        return (_record, ("ran",))


class MemoryStorage:
    """The object storage, as ``ObjectStorageService`` answers: listing a prefix with
    nothing under it is ``ObjectNotFound``, as is reading or deleting a missing key."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.reachable = True
        self.writable = True

    def _check(self) -> None:
        if not self.reachable:
            raise ConnectionError("object storage unreachable")

    def list_objects(self, prefix: str = "") -> list[str]:
        self._check()
        found = [k for k in self.objects if k.startswith(f"{prefix}/")]
        if not found:
            raise Exceptions.ObjectNotFound(prefix)
        return found

    def get_object(self, prefix: str, key: str) -> bytes:
        self._check()
        try:
            return self.objects[f"{prefix}/{key}"]
        except KeyError:
            raise Exceptions.ObjectNotFound(key) from None

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self._check()
        if not self.writable:
            raise PermissionError("read-only")
        self.objects[f"{prefix}/{key}"] = content

    def delete_object(self, prefix: str, key: str) -> None:
        self._check()
        try:
            del self.objects[f"{prefix}/{key}"]
        except KeyError:
            raise Exceptions.ObjectNotFound(key) from None


def _event(event_id: str = "e1") -> dict:
    return {
        "event_id": event_id,
        "timestamp": "2026-11-02T03:04:05Z",
        "session_id": "s1",
        "event_name": "page_viewed",
        "properties": {"n": 1, "tags": ["a"]},
    }


@pytest.fixture
def storage() -> MemoryStorage:
    return MemoryStorage()


def test_no_legacy_files_reads_nothing(storage) -> None:
    assert LegacyAnalyticsStorage(storage).list_events() == []


def test_json_and_pickled_events_are_read_as_plain_data(storage) -> None:
    CALLS.clear()
    storage.objects[f"{EVENTS_PREFIX}/a.json"] = json.dumps(_event("json")).encode()
    storage.objects[f"{EVENTS_PREFIX}/b.pkl"] = pickle.dumps(_event("pickled"))
    storage.objects[f"{EVENTS_PREFIX}/runs.pkl"] = pickle.dumps(_Runs())
    storage.objects[f"{EVENTS_PREFIX}/nested.pkl"] = pickle.dumps(
        {**_event("nested"), "properties": {"x": _Runs()}}
    )
    storage.objects[f"{EVENTS_PREFIX}/broken.json"] = b"{not json"
    storage.objects[f"{EVENTS_PREFIX}/notes.txt"] = b"ignored"
    before = dict(storage.objects)

    events = dict(LegacyAnalyticsStorage(storage).list_events())

    assert CALLS == []  # never read as code
    assert sorted(e["event_id"] for e in events.values() if e) == ["json", "pickled"]
    # The others are named, as unreadable: never skipped silently.
    assert {name for name, e in events.items() if e is None} == {
        "runs.pkl",
        "nested.pkl",
        "broken.json",
        "notes.txt",
    }
    assert storage.objects == before  # reading converts or deletes nothing


def test_an_unreachable_storage_raises(storage) -> None:
    storage.objects[f"{EVENTS_PREFIX}/a.json"] = json.dumps(_event()).encode()
    storage.reachable = False
    with pytest.raises(ConnectionError):
        LegacyAnalyticsStorage(storage).list_events()


def test_the_aggregates_and_the_replayed_raw_events_are_deleted(storage) -> None:
    for name in LEGACY_FILES:
        storage.objects[f"{OUTPUT_DIR}/{name}"] = b"{}"
    storage.objects[f"{EVENTS_PREFIX}/a.json"] = json.dumps(_event()).encode()
    storage.objects[f"{EVENTS_PREFIX}/b.pkl"] = pickle.dumps(_event("b"))
    storage.objects[f"{EVENTS_PREFIX}/c.json"] = json.dumps(_event("c")).encode()
    storage.objects["naas_abi/nexus/other/kept.json"] = b"{}"

    deleted = LegacyAnalyticsStorage(storage).delete_replayed(["a.json", "b.pkl"])

    assert deleted == len(LEGACY_FILES) + 2
    # c.json was not replayed: kept.
    assert sorted(storage.objects) == [
        f"{EVENTS_PREFIX}/c.json",
        "naas_abi/nexus/other/kept.json",
    ]
    assert {
        "events.json",
        "overview.json",
        "users.json",
        "sessions.json",
        "pages.json",
        "workspaces.json",
        "user_details.json",
        "recent_events.json",
        "metadata.json",
    } < set(LEGACY_FILES)
    assert {n for n in LEGACY_FILES if n.startswith("ref-")} == {
        "ref-scenario.json",
        "ref-users.json",
        "ref-workspaces.json",
    }


def test_deleting_what_is_already_gone_is_not_an_error(storage) -> None:
    storage.objects[f"{OUTPUT_DIR}/overview.json"] = b"{}"
    legacy = LegacyAnalyticsStorage(storage)
    assert legacy.delete_replayed(["gone.json"]) == 1
    assert legacy.delete_replayed(["gone.json"]) == 0


def test_unreadable_events_are_moved_aside_never_deleted(storage) -> None:
    storage.objects[f"{EVENTS_PREFIX}/broken.json"] = b"{not json"
    storage.objects[f"{EVENTS_PREFIX}/runs.pkl"] = b"\x80\x04junk"
    legacy = LegacyAnalyticsStorage(storage)

    assert legacy.set_aside(["broken.json", "runs.pkl", "gone.json"]) == 2

    assert storage.objects == {
        f"{UNREADABLE_PREFIX}/broken.json": b"{not json",
        f"{UNREADABLE_PREFIX}/runs.pkl": b"\x80\x04junk",
    }


def test_an_event_that_cannot_be_copied_aside_stays_where_it_is(storage) -> None:
    storage.objects[f"{EVENTS_PREFIX}/broken.json"] = b"{not json"
    storage.writable = False

    assert LegacyAnalyticsStorage(storage).set_aside(["broken.json"]) == 0

    assert storage.objects == {f"{EVENTS_PREFIX}/broken.json": b"{not json"}

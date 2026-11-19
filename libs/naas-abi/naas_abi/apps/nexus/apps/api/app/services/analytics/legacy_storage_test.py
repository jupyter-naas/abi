"""The removed analytics app's object-storage files: read as data, then all deleted."""

from __future__ import annotations

import json
import pickle

import pytest
from naas_abi.apps.nexus.apps.api.app.services.analytics.legacy_storage import (
    EVENTS_PREFIX,
    LEGACY_FILES,
    OUTPUT_DIR,
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

    events = LegacyAnalyticsStorage(storage).list_events()

    assert CALLS == []  # never read as code
    assert sorted(e["event_id"] for e in events) == ["json", "pickled"]
    assert storage.objects == before  # reading converts or deletes nothing


def test_an_unreachable_storage_raises(storage) -> None:
    storage.objects[f"{EVENTS_PREFIX}/a.json"] = json.dumps(_event()).encode()
    storage.reachable = False
    with pytest.raises(ConnectionError):
        LegacyAnalyticsStorage(storage).list_events()


def test_every_aggregate_and_raw_event_is_deleted(storage) -> None:
    for name in LEGACY_FILES:
        storage.objects[f"{OUTPUT_DIR}/{name}"] = b"{}"
    storage.objects[f"{EVENTS_PREFIX}/a.json"] = json.dumps(_event()).encode()
    storage.objects[f"{EVENTS_PREFIX}/b.pkl"] = pickle.dumps(_event("b"))
    storage.objects["naas_abi/nexus/other/kept.json"] = b"{}"

    deleted = LegacyAnalyticsStorage(storage).delete_all()

    assert deleted == len(LEGACY_FILES) + 2
    assert list(storage.objects) == ["naas_abi/nexus/other/kept.json"]
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
    assert legacy.delete_all() == 1
    assert legacy.delete_all() == 0

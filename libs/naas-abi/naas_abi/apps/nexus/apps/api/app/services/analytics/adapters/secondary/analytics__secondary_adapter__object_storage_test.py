"""The object-storage analytics store keeps events as JSON."""

from __future__ import annotations

import json
import pickle

from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__object_storage import (  # noqa: E501
    EVENTS_PREFIX,
    AnalyticsSecondaryAdapterObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.service import AnalyticsService
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
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def list_objects(self, prefix: str = "") -> list[str]:
        return [k for k in self.objects if k.startswith(prefix)]

    def get_object(self, prefix: str, key: str) -> bytes:
        try:
            return self.objects[f"{prefix}/{key}"]
        except KeyError:
            raise Exceptions.ObjectNotFound(key) from None

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[f"{prefix}/{key}"] = content

    def delete_object(self, prefix: str, key: str) -> None:
        del self.objects[f"{prefix}/{key}"]


def _event(event_id: str = "e1") -> dict:
    return {
        "event_id": event_id,
        "timestamp": "2026-01-02T03:04:05Z",
        "session_id": "s1",
        "event_name": "page_view",
        "properties": {"n": 1, "tags": ["a"]},
    }


def test_analytics_events_keep_to_json():
    storage = MemoryStorage()
    adapter = AnalyticsSecondaryAdapterObjectStorage(storage)  # type: ignore[arg-type]

    stored_at = adapter.save_event(_event())
    adapter.save_event(_event())  # content-addressed: idempotent

    assert stored_at.startswith(f"{EVENTS_PREFIX}/") and stored_at.endswith(".json")
    assert list(storage.objects) == [stored_at]
    assert json.loads(storage.objects[stored_at]) == _event()
    assert adapter.list_events() == [_event()]


def test_analytics_legacy_events_keep_to_plain_data():
    CALLS.clear()
    storage = MemoryStorage()
    storage.objects[f"{EVENTS_PREFIX}/plain.pkl"] = pickle.dumps(_event("old"))
    storage.objects[f"{EVENTS_PREFIX}/runs.pkl"] = pickle.dumps(_Runs())
    storage.objects[f"{EVENTS_PREFIX}/nested.pkl"] = pickle.dumps(
        {**_event("nested"), "properties": {"x": _Runs()}}
    )
    adapter = AnalyticsSecondaryAdapterObjectStorage(storage)  # type: ignore[arg-type]

    events = adapter.list_events()

    assert CALLS == []
    assert events == [_event("old")]
    # The plain one is converted once; the others are left, never read as code.
    keys = sorted(storage.objects)
    assert f"{EVENTS_PREFIX}/plain.pkl" not in keys
    assert [k for k in keys if k.endswith(".json")] != []
    assert adapter.list_events() == [_event("old")]
    assert CALLS == []


def test_analytics_rebuild_keeps_stored_events_as_data():
    CALLS.clear()
    storage = MemoryStorage()
    storage.objects[f"{EVENTS_PREFIX}/0123.pkl"] = pickle.dumps(_Runs())
    service = AnalyticsService(
        storage=AnalyticsSecondaryAdapterObjectStorage(storage)  # type: ignore[arg-type]
    )

    service.rebuild()

    assert CALLS == []

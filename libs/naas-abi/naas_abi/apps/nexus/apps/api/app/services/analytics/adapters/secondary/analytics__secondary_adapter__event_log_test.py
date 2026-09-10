"""Tests for the event-log analytics adapter.

The property that matters is fidelity: whatever the tracker sent must come back
out of ``list_events`` byte-identical, because the aggregates are computed from
it and any drift is a silent dashboard regression.
"""

from __future__ import annotations

from typing import Any

import pytest
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary import (
    analytics__secondary_adapter__event_log as event_log_module,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__event_log import (  # noqa: E501
    AnalyticsSecondaryAdapterEventLog,
    reset_legacy_cache,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsStoragePort


class FakeEventService:
    """Stands in for EventService: append on publish, replay on iter_query."""

    def __init__(self) -> None:
        self.records: list[AnalyticsEventRecorded] = []
        self.iter_calls = 0

    def publish(self, record: Any) -> Any:
        self.records.append(record)
        return type("Stored", (), {"seq": len(self.records)})()

    def iter_query(self, event_class: Any = None, **_: Any):
        self.iter_calls += 1
        assert event_class is AnalyticsEventRecorded
        return iter(list(self.records))


class FakeObjectStorageAdapter(AnalyticsStoragePort):
    def __init__(self, legacy: list[dict[str, Any]] | None = None) -> None:
        self.legacy = legacy or []
        self.json: dict[str, Any] = {}
        self.saved_events: list[dict[str, Any]] = []
        self.list_calls = 0

    def save_event(self, event: dict[str, Any]) -> str:
        self.saved_events.append(event)
        return "legacy"

    def list_events(self) -> list[dict[str, Any]]:
        self.list_calls += 1
        return [dict(e) for e in self.legacy]

    def save_json(self, file_name: str, data: Any) -> None:
        self.json[file_name] = data

    def load_json(self, file_name: str, fallback: Any = None) -> Any:
        return self.json.get(file_name, fallback)


def event(event_id: str = "e1", **overrides: Any) -> dict[str, Any]:
    payload = {
        "event_id": event_id,
        "timestamp": "2026-09-09T09:00:00Z",
        "user_id": "u-alice",
        "user_email": "alice@example.com",
        "workspace_id": "ws-1",
        "workspace_name": "Workspace One",
        "session_id": "s1",
        "event_name": "page_viewed",
        "page_path": "/home",
        "page_title": "Home",
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_legacy_cache()
    yield
    reset_legacy_cache()


@pytest.fixture
def storage() -> FakeObjectStorageAdapter:
    fake = FakeObjectStorageAdapter()
    # The service keeps this user directory up to date at ingestion.
    fake.json["ref-users.json"] = [{"user_id": "u-alice", "user_email": "alice@example.com"}]
    return fake


@pytest.fixture
def events() -> FakeEventService:
    return FakeEventService()


@pytest.fixture
def adapter(events: FakeEventService, storage: FakeObjectStorageAdapter):
    return AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=storage)


class TestSaveEvent:
    def test_publishes_instead_of_writing_an_object(self, adapter, events, storage):
        adapter.save_event(event())
        assert len(events.records) == 1
        assert storage.saved_events == []

    def test_returns_the_log_position(self, adapter):
        assert adapter.save_event(event()) == "event-log#seq=1"

    def test_projects_the_queryable_columns(self, adapter, events):
        adapter.save_event(event())
        record = events.records[0]
        assert record.event_id == "e1"
        assert record.event_name == "page_viewed"
        assert record.user_id == "u-alice"
        assert record.workspace_id == "ws-1"
        assert record.session_id == "s1"
        assert record.page_path == "/home"
        assert record.timestamp == "2026-09-09T09:00:00Z"

    def test_a_payload_with_no_known_fields_still_publishes(self, adapter, events):
        adapter.save_event({"anything": 1})
        assert events.records[0].event_id is None


class TestNoEmailInTheLog:
    """The event log is append-only: it keeps the user id, never the email."""

    def test_neither_the_column_nor_the_payload_holds_the_email(self, adapter, events):
        adapter.save_event(event())
        record = events.records[0]
        assert record.user_email is None
        assert "alice@example.com" not in record.payload_json
        assert "user_email" not in record.payload_json

    def test_the_email_comes_back_from_the_user_directory(self, adapter, storage):
        adapter.save_event(event())
        storage.json["ref-users.json"] = [{"user_id": "u-alice", "user_email": "alice.new@example.com"}]
        assert adapter.list_events()[0]["user_email"] == "alice.new@example.com"

    def test_an_unknown_user_comes_back_without_an_email(self, adapter, storage):
        adapter.save_event(event(user_id="u-ghost", user_email="ghost@example.com"))
        assert "user_email" not in adapter.list_events()[0]

    def test_legacy_events_keep_the_email_they_were_written_with(self, events):
        legacy = event("old-1", user_id="u-nobody", user_email="old@example.com")
        storage = FakeObjectStorageAdapter(legacy=[legacy])
        adapter = AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=storage)
        assert adapter.list_events() == [legacy]


class TestListEvents:
    def test_round_trips_the_payload_verbatim(self, adapter):
        original = event()
        adapter.save_event(original)
        assert adapter.list_events() == [original]

    def test_keeps_tracker_fields_the_event_class_does_not_declare(self, adapter):
        original = event(properties={"button": "export"}, country="FR", referrer="google")
        adapter.save_event(original)
        assert adapter.list_events()[0] == original

    def test_returns_every_distinct_event(self, adapter):
        adapter.save_event(event("e1"))
        adapter.save_event(event("e2"))
        assert {e["event_id"] for e in adapter.list_events()} == {"e1", "e2"}

    def test_an_identical_republish_appears_once(self, adapter, events):
        adapter.save_event(event())
        adapter.save_event(event())
        assert len(events.records) == 2
        assert len(adapter.list_events()) == 1

    def test_same_id_with_different_content_is_kept_apart(self, adapter):
        adapter.save_event(event("e1", page_path="/home"))
        adapter.save_event(event("e1", page_path="/settings"))
        assert len(adapter.list_events()) == 2

    def test_an_unreadable_payload_is_skipped_not_fatal(self, adapter, events):
        adapter.save_event(event())
        events.records.append(AnalyticsEventRecorded(event_id="bad", payload_json="{not json"))
        events.records.append(AnalyticsEventRecorded(event_id="empty", payload_json=None))
        assert len(adapter.list_events()) == 1


class TestLegacyUnion:
    def test_history_in_the_pickle_store_stays_visible(self, events):
        storage = FakeObjectStorageAdapter(legacy=[event("old-1"), event("old-2")])
        adapter = AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=storage)
        adapter.save_event(event("new-1"))
        assert {e["event_id"] for e in adapter.list_events()} == {"old-1", "old-2", "new-1"}

    def test_an_event_in_both_stores_appears_once(self, events):
        shared = event("both")
        storage = FakeObjectStorageAdapter(legacy=[shared])
        adapter = AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=storage)
        adapter.save_event(shared)
        assert adapter.list_events() == [shared]

    def test_the_legacy_store_is_read_once_per_process(self, events):
        storage = FakeObjectStorageAdapter(legacy=[event("old-1")])
        adapter = AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=storage)
        for _ in range(3):
            adapter.list_events()
        assert storage.list_calls == 1
        assert events.iter_calls == 3

    def test_a_legacy_read_failure_does_not_empty_the_log(self, events, monkeypatch):
        storage = FakeObjectStorageAdapter()
        monkeypatch.setattr(
            storage, "list_events", lambda: (_ for _ in ()).throw(RuntimeError("minio down"))
        )
        adapter = AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=storage)
        adapter.save_event(event("survivor"))
        assert [e["event_id"] for e in adapter.list_events()] == ["survivor"]

    def test_a_failed_legacy_read_is_retried_rather_than_cached(self, events):
        storage = FakeObjectStorageAdapter(legacy=[event("old-1")])
        calls = {"n": 0}
        real = storage.list_events

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("minio down")
            return real()

        storage.list_events = flaky  # type: ignore[method-assign]
        adapter = AnalyticsSecondaryAdapterEventLog(events=events, object_storage_adapter=storage)
        assert adapter.list_events() == []
        assert [e["event_id"] for e in adapter.list_events()] == ["old-1"]


class TestAggregatesStayInObjectStorage:
    def test_json_is_delegated(self, adapter, storage):
        adapter.save_json("overview.json", {"a": 1})
        assert storage.json["overview.json"] == {"a": 1}
        assert adapter.load_json("overview.json") == {"a": 1}

    def test_a_missing_aggregate_returns_the_fallback(self, adapter):
        assert adapter.load_json("nope.json", fallback={"x": 0}) == {"x": 0}


def test_module_exposes_a_cache_reset():
    assert callable(event_log_module.reset_legacy_cache)

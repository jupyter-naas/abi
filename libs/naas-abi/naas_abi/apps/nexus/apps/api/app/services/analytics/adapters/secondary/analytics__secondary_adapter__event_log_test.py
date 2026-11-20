"""Tests for the event-log analytics adapter.

The property that matters is fidelity: whatever the tracker sent (its email
aside) must come back out of the log as the rollups' consumer reads it, because
the rollups are computed from it.
"""

from __future__ import annotations

from typing import Any

import pytest
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__event_log import (  # noqa: E501
    AnalyticsSecondaryAdapterEventLog,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsEventLogPort
from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import payload_of_log_event


class FakeEventService:
    """Stands in for EventService: append on publish."""

    def __init__(self) -> None:
        self.records: list[AnalyticsEventRecorded] = []

    def publish(self, record: Any) -> Any:
        self.records.append(record)
        return type("Stored", (), {"seq": len(self.records)})()


def event(event_id: str = "e1", **overrides: Any) -> dict[str, Any]:
    payload = {
        "event_id": event_id,
        "timestamp": "2026-09-09T09:00:00Z",
        "user_id": "u-alice",
        "user_email": "alice@example.com",
        "workspace_id": "ws-1",
        "workspace_name": "Workspace One",
        "organization_id": "org-1",
        "session_id": "s1",
        "event_name": "page_viewed",
        "page_path": "/home",
        "page_title": "Home",
        "properties": {"n": 1, "tags": ["a"]},
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def events() -> FakeEventService:
    return FakeEventService()


@pytest.fixture
def adapter(events: FakeEventService) -> AnalyticsSecondaryAdapterEventLog:
    return AnalyticsSecondaryAdapterEventLog(events=events)


def test_it_is_the_ingest_s_log_port(adapter) -> None:
    assert isinstance(adapter, AnalyticsEventLogPort)


class TestSaveEvent:
    def test_publishes_one_record(self, adapter, events):
        adapter.save_event(event())
        assert len(events.records) == 1
        assert isinstance(events.records[0], AnalyticsEventRecorded)

    def test_returns_the_log_position(self, adapter):
        assert adapter.save_event(event()) == "event-log#seq=1"

    def test_projects_the_queryable_columns(self, adapter, events):
        adapter.save_event(event())
        record = events.records[0]
        assert record.event_id == "e1"
        assert record.event_name == "page_viewed"
        assert record.user_id == "u-alice"
        assert record.workspace_id == "ws-1"
        assert record.organization_id == "org-1"
        assert record.session_id == "s1"
        assert record.page_path == "/home"
        assert record.timestamp == "2026-09-09T09:00:00Z"

    def test_a_payload_with_no_known_fields_still_publishes(self, adapter, events):
        adapter.save_event({"anything": 1})
        assert events.records[0].event_id is None

    def test_the_consumer_reads_the_payload_back_verbatim(self, adapter, events):
        adapter.save_event(event())
        expected = {k: v for k, v in event().items() if k != "user_email"}
        assert payload_of_log_event(events.records[0]) == expected


class TestNoEmailInTheLog:
    """The event log is append-only: it keeps the user id, never the email."""

    def test_neither_the_column_nor_the_payload_holds_the_email(self, adapter, events):
        adapter.save_event(event())
        record = events.records[0]
        assert record.user_email is None
        assert "alice@example.com" not in record.payload_json
        assert "user_email" not in record.payload_json

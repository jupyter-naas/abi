from datetime import datetime, timezone

import pytest
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
)
from pydantic import ValidationError


def test_activity_event_minimal_construction():
    event = ActivityEvent(actor_id="user:abc", event_type="http.request")
    assert event.actor_id == "user:abc"
    assert event.event_type == "http.request"
    assert event.correlation_id is None
    assert event.attributes == {}
    assert event.timestamp.tzinfo is not None


def test_activity_event_default_timestamp_is_utc_now():
    before = datetime.now(timezone.utc)
    event = ActivityEvent(actor_id="x", event_type="y")
    after = datetime.now(timezone.utc)
    assert before <= event.timestamp <= after


def test_activity_event_accepts_full_payload():
    ts = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    event = ActivityEvent(
        actor_id="user:123",
        event_type="http.request",
        timestamp=ts,
        correlation_id="req-abc",
        attributes={"method": "GET", "path": "/foo", "status": 200},
    )
    assert event.timestamp == ts
    assert event.correlation_id == "req-abc"
    assert event.attributes["status"] == 200


def test_activity_event_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ActivityEvent(actor_id="x", event_type="y", unexpected="oops")  # type: ignore[call-arg]


def test_activity_log_query_defaults():
    q = ActivityLogQuery()
    assert q.event_type is None
    assert q.since is None
    assert q.until is None
    assert q.limit is None


def test_activity_log_query_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ActivityLogQuery(foo="bar")  # type: ignore[call-arg]

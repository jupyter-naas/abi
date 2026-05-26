from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
)


class GenericActivityLogSecondaryAdapterTest(ABC):
    """Reusable test suite for any IActivityLogAdapter implementation.

    Concrete adapter test classes subclass this and provide the
    ``adapter`` and ``adapter_class`` fixtures.
    """

    @pytest.fixture
    @abstractmethod
    def adapter_class(self):
        raise NotImplementedError()

    @pytest.fixture
    @abstractmethod
    def adapter(self):
        """Yield a fresh adapter instance backed by ephemeral storage."""
        raise NotImplementedError()

    def test_adapter_has_required_methods(self, adapter_class):
        assert callable(getattr(adapter_class, "record", None))
        assert callable(getattr(adapter_class, "query", None))
        assert callable(getattr(adapter_class, "list_actors", None))
        assert callable(getattr(adapter_class, "shutdown", None))

    def test_record_then_query_round_trip(self, adapter):
        actor = f"user:{uuid4()}"
        event = ActivityEvent(
            actor_id=actor,
            event_type="http.request",
            correlation_id="req-1",
            attributes={"method": "GET", "path": "/x", "status": 200},
        )
        adapter.record(event)

        events = adapter.query(actor)
        assert len(events) == 1
        got = events[0]
        assert got.actor_id == actor
        assert got.event_type == "http.request"
        assert got.correlation_id == "req-1"
        assert got.attributes == {"method": "GET", "path": "/x", "status": 200}

    def test_query_returns_events_ordered_by_timestamp_ascending(self, adapter):
        actor = f"user:{uuid4()}"
        base = datetime.now(timezone.utc)
        for i in range(5):
            adapter.record(
                ActivityEvent(
                    actor_id=actor,
                    event_type="x",
                    timestamp=base + timedelta(seconds=i),
                    attributes={"i": i},
                )
            )

        events = adapter.query(actor)
        assert [e.attributes["i"] for e in events] == [0, 1, 2, 3, 4]

    def test_query_unknown_actor_returns_empty(self, adapter):
        assert adapter.query(f"user:{uuid4()}") == []

    def test_actors_are_isolated(self, adapter):
        a, b = f"user:{uuid4()}", f"user:{uuid4()}"
        adapter.record(ActivityEvent(actor_id=a, event_type="x"))
        adapter.record(ActivityEvent(actor_id=a, event_type="x"))
        adapter.record(ActivityEvent(actor_id=b, event_type="x"))

        assert len(adapter.query(a)) == 2
        assert len(adapter.query(b)) == 1

    def test_query_filters_by_event_type(self, adapter):
        actor = f"user:{uuid4()}"
        adapter.record(ActivityEvent(actor_id=actor, event_type="http.request"))
        adapter.record(ActivityEvent(actor_id=actor, event_type="http.request"))
        adapter.record(ActivityEvent(actor_id=actor, event_type="triple_store.insert"))

        results = adapter.query(actor, ActivityLogQuery(event_type="http.request"))
        assert len(results) == 2
        assert all(e.event_type == "http.request" for e in results)

    def test_query_filters_by_time_range(self, adapter):
        actor = f"user:{uuid4()}"
        t0 = datetime.now(timezone.utc)
        for i in range(5):
            adapter.record(
                ActivityEvent(
                    actor_id=actor,
                    event_type="x",
                    timestamp=t0 + timedelta(seconds=i),
                    attributes={"i": i},
                )
            )

        since = t0 + timedelta(seconds=1)
        until = t0 + timedelta(seconds=3)
        results = adapter.query(actor, ActivityLogQuery(since=since, until=until))
        assert [e.attributes["i"] for e in results] == [1, 2, 3]

    def test_query_applies_limit(self, adapter):
        actor = f"user:{uuid4()}"
        for i in range(10):
            adapter.record(
                ActivityEvent(
                    actor_id=actor,
                    event_type="x",
                    attributes={"i": i},
                )
            )
        results = adapter.query(actor, ActivityLogQuery(limit=3))
        assert len(results) == 3

    def test_list_actors_returns_known_actors(self, adapter):
        a, b = f"user:{uuid4()}", f"user:{uuid4()}"
        adapter.record(ActivityEvent(actor_id=a, event_type="x"))
        adapter.record(ActivityEvent(actor_id=b, event_type="x"))

        actors = adapter.list_actors()
        assert a in actors
        assert b in actors

    def test_attributes_preserve_nested_json(self, adapter):
        actor = f"user:{uuid4()}"
        attrs = {
            "nested": {"deep": [1, 2, {"k": "v"}]},
            "null": None,
            "bool": True,
            "float": 1.5,
        }
        adapter.record(
            ActivityEvent(actor_id=actor, event_type="x", attributes=attrs)
        )
        results = adapter.query(actor)
        assert results[0].attributes == attrs

    def test_actor_id_with_unusual_characters(self, adapter):
        # actor_id is opaque — adapters must handle anything reasonable
        # (slashes, colons, spaces, unicode).
        actor = f"weird/actor: {uuid4()} é"
        adapter.record(ActivityEvent(actor_id=actor, event_type="x"))
        results = adapter.query(actor)
        assert len(results) == 1
        assert results[0].actor_id == actor

    def test_shutdown_is_idempotent(self, adapter):
        adapter.shutdown()
        adapter.shutdown()

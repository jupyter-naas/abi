"""Tests for EventService."""

from __future__ import annotations

import threading
from typing import Callable, ClassVar, Optional

from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.event_ontology import LogProcess
from naas_abi_core.services.event.EventPort import InvalidEventError
from naas_abi_core.services.event.EventService import EventService, class_iri_to_topic


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeBusAdapter(IBusAdapter):
    """Records publishes; topic_consume registers a callback synchronously."""

    def __init__(self):
        self.published: list[tuple[str, str, bytes]] = []
        self._subscribers: dict[str, list[Callable[[bytes], None]]] = {}

    def topic_publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        self.published.append((topic, routing_key, payload))
        for cb in self._subscribers.get(topic, []):
            cb(payload)

    def topic_consume(self, topic, routing_key, callback):
        self._subscribers.setdefault(topic, []).append(callback)
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t


# A concrete subclass of LogProcess for testing.
class UserAuthenticated(LogProcess):
    _class_uri: ClassVar[str] = "http://example.org/UserAuthenticated"
    _property_uris: ClassVar[dict] = {
        **LogProcess._property_uris,
        "user_id": "http://example.org/userId",
    }
    user_id: Optional[str] = None


# A non-LogProcess type, for the rejection test.
class _NotAnEvent:
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_service(tmp_path):
    adapter = EventSQLiteAdapter(str(tmp_path / "events.sqlite"))
    bus_adapter = _FakeBusAdapter()
    bus = BusService(bus_adapter)
    service = EventService(adapter=adapter, bus=bus)
    return service, adapter, bus_adapter


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


def test_publish_persists_and_broadcasts(tmp_path):
    service, adapter, bus_adapter = _make_service(tmp_path)

    evt = UserAuthenticated(user_id="alice")
    stored = service.publish(evt)

    assert stored.event_type == UserAuthenticated._class_uri
    assert stored.id == evt._uri
    assert stored.seq == 1

    # Persisted
    rows = adapter.query()
    assert len(rows) == 1
    assert rows[0].payload == stored.payload

    # Broadcast on the bus under the hashed topic
    assert len(bus_adapter.published) == 1
    topic, routing_key, payload = bus_adapter.published[0]
    assert topic == class_iri_to_topic(UserAuthenticated._class_uri)
    assert payload == stored.payload


def test_publish_rejects_non_log_process(tmp_path):
    service, _, _ = _make_service(tmp_path)
    try:
        service.publish(_NotAnEvent())
    except InvalidEventError:
        return
    raise AssertionError("expected InvalidEventError")


def test_publish_persists_even_if_bus_fails(tmp_path):
    service, adapter, bus_adapter = _make_service(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("bus down")

    bus_adapter.topic_publish = boom  # type: ignore[assignment]

    evt = UserAuthenticated(user_id="bob")
    stored = service.publish(evt)
    assert stored.seq == 1
    assert len(adapter.query()) == 1


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


def test_query_reconstructs_instances(tmp_path):
    service, _, _ = _make_service(tmp_path)

    e1 = UserAuthenticated(user_id="alice")
    e2 = UserAuthenticated(user_id="bob")
    service.publish(e1)
    service.publish(e2)

    results = service.query(event_class=UserAuthenticated)
    assert len(results) == 2
    assert all(isinstance(r, UserAuthenticated) for r in results)
    user_ids = sorted(r.user_id for r in results)
    assert user_ids == ["alice", "bob"]


def test_query_without_event_class_returns_log_process(tmp_path):
    service, _, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice"))
    results = service.query()
    assert len(results) == 1
    assert isinstance(results[0], LogProcess)


# ---------------------------------------------------------------------------
# query_for_consumer
# ---------------------------------------------------------------------------


def test_query_for_consumer_advances_cursor(tmp_path):
    service, _, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice"))
    service.publish(UserAuthenticated(user_id="bob"))

    first = service.query_for_consumer("worker-1", UserAuthenticated)
    assert sorted(e.user_id for e in first) == ["alice", "bob"]

    second = service.query_for_consumer("worker-1", UserAuthenticated)
    assert second == []


# ---------------------------------------------------------------------------
# iter_query
# ---------------------------------------------------------------------------


def test_iter_query_streams_all_events(tmp_path):
    service, _, _ = _make_service(tmp_path)
    for i in range(7):
        service.publish(UserAuthenticated(user_id=f"u{i}"))

    streamed = list(service.iter_query(event_class=UserAuthenticated, batch_size=3))
    assert len(streamed) == 7
    assert sorted(e.user_id for e in streamed) == [f"u{i}" for i in range(7)]


def test_iter_query_is_a_lazy_iterator(tmp_path):
    service, _, _ = _make_service(tmp_path)
    for i in range(5):
        service.publish(UserAuthenticated(user_id=f"u{i}"))

    it = service.iter_query(event_class=UserAuthenticated, batch_size=2)
    # It's an iterator, not a list — consuming one item must work.
    first = next(it)
    assert isinstance(first, UserAuthenticated)
    # Remaining are still yieldable.
    rest = list(it)
    assert len(rest) == 4


def test_iter_query_snapshot_semantics(tmp_path):
    """Events appended during iteration are not included."""
    service, _, _ = _make_service(tmp_path)
    for i in range(3):
        service.publish(UserAuthenticated(user_id=f"u{i}"))

    it = service.iter_query(event_class=UserAuthenticated, batch_size=1)
    seen = []
    seen.append(next(it).user_id)

    # Append more between yields — they must NOT appear in this iteration.
    service.publish(UserAuthenticated(user_id="appended-mid-iteration"))

    seen.extend(e.user_id for e in it)
    assert sorted(seen) == ["u0", "u1", "u2"]


def test_iter_query_empty(tmp_path):
    service, _, _ = _make_service(tmp_path)
    assert list(service.iter_query(event_class=UserAuthenticated)) == []


def test_iter_query_respects_limit(tmp_path):
    service, _, _ = _make_service(tmp_path)
    for i in range(10):
        service.publish(UserAuthenticated(user_id=f"u{i}"))

    streamed = list(
        service.iter_query(event_class=UserAuthenticated, limit=3, batch_size=2)
    )
    assert [e.user_id for e in streamed] == ["u0", "u1", "u2"]


def test_iter_query_limit_zero_yields_nothing(tmp_path):
    service, _, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice"))
    assert list(service.iter_query(event_class=UserAuthenticated, limit=0)) == []


def test_iter_query_for_consumer_respects_limit(tmp_path):
    service, adapter, _ = _make_service(tmp_path)
    for i in range(10):
        service.publish(UserAuthenticated(user_id=f"u{i}"))

    first = list(
        service.iter_query_for_consumer(
            "worker-1", UserAuthenticated, limit=4, batch_size=3
        )
    )
    assert [e.user_id for e in first] == ["u0", "u1", "u2", "u3"]
    # Cursor advanced over only what we actually consumed.
    assert adapter.get_cursor("worker-1", UserAuthenticated._class_uri) == 4

    rest = list(
        service.iter_query_for_consumer("worker-1", UserAuthenticated, batch_size=3)
    )
    assert [e.user_id for e in rest] == [f"u{i}" for i in range(4, 10)]


def test_iter_query_respects_since_seq(tmp_path):
    service, _, _ = _make_service(tmp_path)
    stored = [service.publish(UserAuthenticated(user_id=f"u{i}")) for i in range(5)]

    streamed = list(
        service.iter_query(
            event_class=UserAuthenticated,
            since_seq=stored[1].seq,  # skip first two
            batch_size=2,
        )
    )
    assert [e.user_id for e in streamed] == ["u2", "u3", "u4"]


# ---------------------------------------------------------------------------
# iter_query_for_consumer
# ---------------------------------------------------------------------------


def test_iter_query_for_consumer_drains_across_batches(tmp_path):
    service, _, _ = _make_service(tmp_path)
    for i in range(10):
        service.publish(UserAuthenticated(user_id=f"u{i}"))

    streamed = list(
        service.iter_query_for_consumer(
            "worker-1", UserAuthenticated, batch_size=3
        )
    )
    assert [e.user_id for e in streamed] == [f"u{i}" for i in range(10)]

    # Cursor is fully advanced — second call yields nothing.
    assert list(
        service.iter_query_for_consumer("worker-1", UserAuthenticated, batch_size=3)
    ) == []


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------


def test_subscribe_routes_to_bus(tmp_path):
    service, _, bus_adapter = _make_service(tmp_path)

    received: list[UserAuthenticated] = []

    def cb(evt: UserAuthenticated) -> None:
        received.append(evt)

    service.subscribe(UserAuthenticated, cb)
    service.publish(UserAuthenticated(user_id="alice"))

    assert len(received) == 1
    assert isinstance(received[0], UserAuthenticated)
    assert received[0].user_id == "alice"


# ---------------------------------------------------------------------------
# topic hashing
# ---------------------------------------------------------------------------


def test_class_iri_to_topic_is_deterministic_and_short():
    iri = "http://example.org/UserAuthenticated"
    t1 = class_iri_to_topic(iri)
    t2 = class_iri_to_topic(iri)
    assert t1 == t2
    assert len(t1) <= 64
    assert "://" not in t1 and "#" not in t1

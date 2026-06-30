"""Tests for EventService."""

from __future__ import annotations

import threading
from typing import Callable, ClassVar, Optional

from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from naas_abi_core.services.event.EventPort import InvalidEventError
from naas_abi_core.services.event.EventService import EventService, class_iri_to_topic


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeBusAdapter(IBusAdapter):
    """Records publishes; subscribe registers callbacks synchronously and
    delivers to ALL of them per publish (pub/sub fanout)."""

    def __init__(self):
        self.published: list[tuple[str, str, bytes]] = []
        self.enqueued: list[tuple[str, str, bytes]] = []
        self._subscribers: dict[str, list[Callable[[bytes], None]]] = {}
        self._workers: dict[str, list[Callable[[bytes], None]]] = {}

    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        self.published.append((topic, routing_key, payload))
        for cb in self._subscribers.get(topic, []):
            cb(payload)

    def subscribe(self, topic, routing_key, callback):
        self._subscribers.setdefault(topic, []).append(callback)
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t

    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        self.enqueued.append((topic, routing_key, payload))

    def dequeue(self, topic, routing_key, callback):
        self._workers.setdefault(topic, []).append(callback)
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

    # Pub/sub-published on the bus under the hashed topic
    assert len(bus_adapter.published) == 1
    topic, routing_key, payload = bus_adapter.published[0]
    assert topic == class_iri_to_topic(UserAuthenticated._class_uri)
    assert routing_key == evt._uri
    assert payload == stored.payload


def test_publish_rejects_non_log_process(tmp_path):
    service, _, _ = _make_service(tmp_path)
    try:
        service.publish(_NotAnEvent())
    except InvalidEventError:
        return
    raise AssertionError("expected InvalidEventError")


def test_publish_populates_created_at_if_unset(tmp_path):
    import datetime as _dt

    service, _, _ = _make_service(tmp_path)

    evt = UserAuthenticated(user_id="alice")
    assert evt.created_at is None  # unset before publish

    before = _dt.datetime.now()
    service.publish(evt)
    after = _dt.datetime.now()

    assert evt.created_at is not None
    assert before <= evt.created_at <= after


def test_publish_preserves_caller_supplied_created_at(tmp_path):
    import datetime as _dt

    service, _, _ = _make_service(tmp_path)

    ts = _dt.datetime(2020, 1, 1, 12, 0, 0)
    evt = UserAuthenticated(user_id="alice", created_at=ts)
    service.publish(evt)
    assert evt.created_at == ts


def test_reconstructed_instance_round_trips_created_at(tmp_path):
    import datetime as _dt

    service, _, _ = _make_service(tmp_path)
    ts = _dt.datetime(2020, 1, 1, 12, 0, 0)
    service.publish(UserAuthenticated(user_id="alice", created_at=ts))

    [evt] = service.query(event_class=UserAuthenticated)
    assert evt.created_at == ts


def test_reconstructed_instance_exposes_storage_metadata(tmp_path):
    service, _, _ = _make_service(tmp_path)
    stored = service.publish(UserAuthenticated(user_id="alice"))

    [evt] = service.query(event_class=UserAuthenticated)
    assert evt._seq == stored.seq
    assert evt._stored_at == stored.timestamp


def test_publish_persists_even_if_bus_fails(tmp_path):
    service, adapter, bus_adapter = _make_service(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("bus down")

    bus_adapter.publish = boom  # type: ignore[assignment]

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
# JSON codec / schema drift
# ---------------------------------------------------------------------------


def test_stored_payload_includes_class_uri_and_property_uris(tmp_path):
    import json

    service, adapter, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice"))

    (row,) = adapter.query()
    doc = json.loads(row.payload)
    assert doc["_class_uri"] == UserAuthenticated._class_uri
    assert doc["user_id"] == "alice"
    # _property_uris embedded so future renames can still map back to IRIs.
    assert "user_id" in doc["_property_uris"]
    assert doc["_property_uris"]["user_id"] == "http://example.org/userId"


def test_reconstruction_drops_fields_no_longer_on_class(tmp_path):
    """Forward-compat: dropping a field from the class doesn't break reading old events."""
    import json
    from naas_abi_core.services.event.EventCodec import deserialize

    service, adapter, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice"))

    (row,) = adapter.query()
    doc = json.loads(row.payload)
    # Simulate a stored event that has an extra field the current class no longer has.
    doc["legacy_field"] = "legacy-value"
    altered = json.dumps(doc).encode("utf-8")

    instance = deserialize(altered, hint_class=UserAuthenticated)
    assert instance.user_id == "alice"  # known field survives
    assert not hasattr(instance, "legacy_field")  # unknown field dropped


# ---------------------------------------------------------------------------
# filter (EventBridge-style)
# ---------------------------------------------------------------------------


def test_query_filter_equals(tmp_path):
    service, _, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice"))
    service.publish(UserAuthenticated(user_id="bob"))

    rows = service.query(event_class=UserAuthenticated, filter={"user_id": "alice"})
    assert [r.user_id for r in rows] == ["alice"]


def test_query_filter_in(tmp_path):
    service, _, _ = _make_service(tmp_path)
    for uid in ("alice", "bob", "carol", "dave"):
        service.publish(UserAuthenticated(user_id=uid))

    rows = service.query(
        event_class=UserAuthenticated, filter={"user_id": ["alice", "carol"]}
    )
    assert sorted(r.user_id for r in rows) == ["alice", "carol"]


def test_query_filter_operators(tmp_path):
    service, _, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice-1"))
    service.publish(UserAuthenticated(user_id="alice-2"))
    service.publish(UserAuthenticated(user_id="bob"))

    rows = service.query(
        event_class=UserAuthenticated, filter={"user_id": {"prefix": "alice"}}
    )
    assert sorted(r.user_id for r in rows) == ["alice-1", "alice-2"]

    rows = service.query(
        event_class=UserAuthenticated, filter={"user_id": {"contains": "lic"}}
    )
    assert sorted(r.user_id for r in rows) == ["alice-1", "alice-2"]

    rows = service.query(
        event_class=UserAuthenticated, filter={"user_id": {"ne": "bob"}}
    )
    assert sorted(r.user_id for r in rows) == ["alice-1", "alice-2"]


def test_query_for_consumer_pushes_down_filter(tmp_path):
    service, _, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice-1"))
    service.publish(UserAuthenticated(user_id="bob"))
    service.publish(UserAuthenticated(user_id="alice-2"))

    rows = service.query_for_consumer(
        "c1", UserAuthenticated, filter={"user_id": {"prefix": "alice"}}
    )
    assert sorted(r.user_id for r in rows) == ["alice-1", "alice-2"]

    # Cursor advanced past the last matching seq (alice-2 @ seq 3), so the
    # non-matching "bob" below it is skipped permanently for this consumer.
    assert service.query_for_consumer(
        "c1", UserAuthenticated, filter={"user_id": {"prefix": "alice"}}
    ) == []
    assert service.query_for_consumer("c1", UserAuthenticated) == []


def test_query_for_consumer_filter_trailing_nonmatch_stays_pending(tmp_path):
    # The SAFE half of the cursor contract: a non-matching event published
    # ABOVE the last match must stay pending — the cursor only advances to the
    # last matching seq, so a later drain still delivers it.
    service, adapter, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice-1"))  # seq 1, matches
    service.publish(UserAuthenticated(user_id="bob"))      # seq 2, trailing non-match

    rows = service.query_for_consumer(
        "c1", UserAuthenticated, filter={"user_id": {"prefix": "alice"}}
    )
    assert [r.user_id for r in rows] == ["alice-1"]
    # Cursor parked at seq 1 (the last match), NOT at the table max.
    assert adapter.get_cursor("c1", UserAuthenticated._class_uri) == 1

    # bob (seq 2) is above the last match, so it is still pending for a later drain.
    rest = service.query_for_consumer("c1", UserAuthenticated)
    assert [r.user_id for r in rest] == ["bob"]


def test_iter_query_for_consumer_pushes_down_filter(tmp_path):
    service, adapter, _ = _make_service(tmp_path)
    # Interleave matching/non-matching events across more than one batch.
    for i in range(6):
        service.publish(UserAuthenticated(user_id=f"alice-{i}"))  # matches
        service.publish(UserAuthenticated(user_id=f"bob-{i}"))    # non-match

    streamed = list(
        service.iter_query_for_consumer(
            "c1",
            UserAuthenticated,
            batch_size=2,
            filter={"user_id": {"prefix": "alice"}},
        )
    )
    # Only matching events stream, in seq order, across multiple batches; the
    # interleaved non-matching events never surface and never blow the budget.
    assert [e.user_id for e in streamed] == [f"alice-{i}" for i in range(6)]
    # Cursor advanced to the last matching seq (alice-5 @ seq 11), leaving the
    # trailing non-match (bob-5 @ seq 12) pending.
    assert adapter.get_cursor("c1", UserAuthenticated._class_uri) == 11

    # A second filtered drain is empty (no matching events remain).
    assert list(
        service.iter_query_for_consumer(
            "c1", UserAuthenticated, filter={"user_id": {"prefix": "alice"}}
        )
    ) == []


def test_query_filter_multiple_keys_anded(tmp_path):
    service, _, _ = _make_service(tmp_path)
    service.publish(UserAuthenticated(user_id="alice"))
    service.publish(UserAuthenticated(user_id="alice"))  # different _uri
    service.publish(UserAuthenticated(user_id="bob"))

    # _uri varies per instance; filter both for an empty-set check.
    rows = service.query(
        event_class=UserAuthenticated,
        filter={"user_id": "alice", "_uri": "nope"},
    )
    assert rows == []


def test_iter_query_filter(tmp_path):
    service, _, _ = _make_service(tmp_path)
    for uid in ("alice", "bob", "alice", "carol", "alice"):
        service.publish(UserAuthenticated(user_id=uid))

    streamed = list(
        service.iter_query(
            event_class=UserAuthenticated,
            filter={"user_id": "alice"},
            batch_size=2,
        )
    )
    assert [e.user_id for e in streamed] == ["alice", "alice", "alice"]


def test_subscribe_with_filter(tmp_path):
    service, _, _ = _make_service(tmp_path)
    received: list[str] = []

    service.subscribe(
        UserAuthenticated,
        lambda e: received.append(e.user_id),
        filter={"user_id": "alice"},
    )

    service.publish(UserAuthenticated(user_id="alice"))
    service.publish(UserAuthenticated(user_id="bob"))
    service.publish(UserAuthenticated(user_id="alice"))

    assert received == ["alice", "alice"]


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


# ---------------------------------------------------------------------------
# Fanout: multiple subscribers each receive every event
# ---------------------------------------------------------------------------


def test_subscribe_fanout_across_multiple_subscribers(tmp_path):
    """Two subscribers on the same event class must each receive every
    published event (Redis-style pub/sub). Regression for the work-queue
    semantics that previously dropped messages to the second subscriber."""
    import time
    from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
        PythonQueueAdapter,
    )

    bus_adapter = PythonQueueAdapter(
        persistence_path=str(tmp_path / "bus.sqlite"),
        poll_interval_seconds=0.01,
    )
    bus = BusService(bus_adapter)
    service = EventService(
        adapter=EventSQLiteAdapter(str(tmp_path / "events.sqlite")),
        bus=bus,
    )

    received_unfiltered: list[str] = []
    received_pdf_only: list[str] = []
    unfiltered_done = threading.Event()
    pdf_done = threading.Event()

    def cb_all(evt):
        received_unfiltered.append(evt.user_id)
        if len(received_unfiltered) == 3:
            unfiltered_done.set()

    def cb_pdf(evt):
        received_pdf_only.append(evt.user_id)
        pdf_done.set()

    service.subscribe(UserAuthenticated, cb_all)
    service.subscribe(
        UserAuthenticated,
        cb_pdf,
        filter={"user_id": {"suffix": ".pdf"}},
    )

    # Let the subscriber loops capture initial cursor.
    time.sleep(0.05)

    service.publish(UserAuthenticated(user_id="alice"))
    service.publish(UserAuthenticated(user_id="report.pdf"))
    service.publish(UserAuthenticated(user_id="bob"))

    assert unfiltered_done.wait(timeout=2)
    assert pdf_done.wait(timeout=2)
    assert received_unfiltered == ["alice", "report.pdf", "bob"]
    assert received_pdf_only == ["report.pdf"]

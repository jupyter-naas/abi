# mypy: disable-error-code="arg-type,misc"
"""Tests for BusService event emission."""

from __future__ import annotations

from collections.abc import Callable
from threading import Thread

import pytest
from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.bus.ontologies.modules.BusEventOntology import (
    BusError,
    BusMessageEnqueued,
    BusMessagePublished,
)


class _FakeAdapter(IBusAdapter):
    def __init__(self) -> None:
        self.published: list[tuple[str, str, bytes]] = []
        self.enqueued: list[tuple[str, str, bytes]] = []
        self.publish_raises: Exception | None = None
        self.enqueue_raises: Exception | None = None
        self.publish_many_calls = 0

    def publish(self, topic: str, routing_key: str, payload: bytes) -> None:
        if self.publish_raises is not None:
            raise self.publish_raises
        self.published.append((topic, routing_key, payload))

    def publish_many(self, topic: str, messages) -> None:
        self.publish_many_calls += 1
        if self.publish_raises is not None:
            raise self.publish_raises
        for routing_key, payload in messages:
            self.published.append((topic, routing_key, payload))

    def subscribe(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        raise NotImplementedError()

    def enqueue(self, topic: str, routing_key: str, payload: bytes) -> None:
        if self.enqueue_raises is not None:
            raise self.enqueue_raises
        self.enqueued.append((topic, routing_key, payload))

    def dequeue(
        self, topic: str, routing_key: str, callback: Callable[[bytes], None]
    ) -> Thread:
        raise NotImplementedError()


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _FakeServices:
    def __init__(self, events: _FakeEventService | None = None) -> None:
        self._events = events

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self) -> _FakeEventService:
        assert self._events is not None
        return self._events


def _wired(emit_message_events: bool = True) -> tuple[_FakeAdapter, BusService, _FakeEventService]:
    # Per-message telemetry is off by default (see BusService docstring); the
    # tests below that assert on it opt in explicitly.
    adapter = _FakeAdapter()
    svc = BusService(adapter, emit_message_events=emit_message_events)
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))
    return adapter, svc, events


# ---------------------------------------------------------------------------
# No events when not wired / events unavailable
# ---------------------------------------------------------------------------


def test_no_events_when_services_not_wired() -> None:
    adapter = _FakeAdapter()
    svc = BusService(adapter)
    svc.publish("topic.x", "rk", b"hello")
    svc.enqueue("topic.x", "rk", b"hello")
    assert adapter.published == [("topic.x", "rk", b"hello")]
    assert adapter.enqueued == [("topic.x", "rk", b"hello")]


def test_no_events_when_events_unavailable() -> None:
    adapter = _FakeAdapter()
    svc = BusService(adapter)
    svc.set_services(_FakeServices(events=None))
    svc.publish("topic.x", "rk", b"hello")
    svc.enqueue("topic.x", "rk", b"hello")
    # Adapter still called, but no events service to publish to.
    assert adapter.published == [("topic.x", "rk", b"hello")]


# ---------------------------------------------------------------------------
# publish / enqueue emit events
# ---------------------------------------------------------------------------


def test_publish_emits_bus_message_published() -> None:
    _adapter, svc, events = _wired()
    svc.publish("topic.x", "key.a", b"hello")

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, BusMessagePublished)
    assert evt.topic == "topic.x"
    assert evt.routing_key == "key.a"
    assert evt.size_bytes == len(b"hello")


def test_enqueue_emits_bus_message_enqueued() -> None:
    _adapter, svc, events = _wired()
    svc.enqueue("jobs.x", "rk.1", b"payload")

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, BusMessageEnqueued)
    assert evt.topic == "jobs.x"
    assert evt.routing_key == "rk.1"
    assert evt.size_bytes == len(b"payload")


# ---------------------------------------------------------------------------
# Per-message telemetry is opt-in — the bus is a hot path.
# ---------------------------------------------------------------------------


def test_publish_emits_no_event_by_default() -> None:
    adapter, svc, events = _wired(emit_message_events=False)
    svc.publish("topic.x", "key.a", b"hello")
    svc.enqueue("jobs.x", "rk.1", b"payload")

    # Messages still reach the adapter; they just don't each become a
    # durable event-log row.
    assert adapter.published == [("topic.x", "key.a", b"hello")]
    assert adapter.enqueued == [("jobs.x", "rk.1", b"payload")]
    assert events.published == []


def test_publish_failure_still_emits_bus_error_when_telemetry_off() -> None:
    adapter, svc, events = _wired(emit_message_events=False)
    adapter.publish_raises = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        svc.publish("topic.x", "rk", b"data")

    errors = [e for e in events.published if isinstance(e, BusError)]
    assert len(errors) == 1
    assert errors[0].operation == "publish"


# ---------------------------------------------------------------------------
# publish_many — same delivery as a publish loop, one adapter round-trip.
# ---------------------------------------------------------------------------


def test_publish_many_forwards_every_message_in_order() -> None:
    adapter, svc, _events = _wired(emit_message_events=False)
    svc.publish_many("triple_store", [("rk.a", b"one"), ("rk.b", b"two")])

    assert adapter.published == [
        ("triple_store", "rk.a", b"one"),
        ("triple_store", "rk.b", b"two"),
    ]
    # One batched adapter call, not one per message.
    assert adapter.publish_many_calls == 1


def test_publish_many_empty_is_a_noop() -> None:
    adapter, svc, events = _wired()
    svc.publish_many("triple_store", [])

    assert adapter.published == []
    assert adapter.publish_many_calls == 0
    assert events.published == []


def test_publish_many_emits_one_event_per_message_when_enabled() -> None:
    _adapter, svc, events = _wired(emit_message_events=True)
    svc.publish_many("triple_store", [("rk.a", b"one"), ("rk.b", b"two")])

    assert [type(e) for e in events.published] == [
        BusMessagePublished,
        BusMessagePublished,
    ]
    assert [e.routing_key for e in events.published] == ["rk.a", "rk.b"]


def test_publish_many_evt_topic_emits_nothing() -> None:
    adapter, svc, events = _wired(emit_message_events=True)
    svc.publish_many("evt.abc123", [("id-1", b"x")])

    assert adapter.published == [("evt.abc123", "id-1", b"x")]
    assert events.published == []


def test_publish_many_failure_emits_bus_error_and_reraises() -> None:
    adapter, svc, events = _wired()
    adapter.publish_raises = RuntimeError("batch down")

    with pytest.raises(RuntimeError):
        svc.publish_many("triple_store", [("rk.a", b"one")])

    errors = [e for e in events.published if isinstance(e, BusError)]
    assert len(errors) == 1
    assert errors[0].operation == "publish_many"


# ---------------------------------------------------------------------------
# Recursion guard — topics starting with "evt." emit nothing.
# ---------------------------------------------------------------------------


def test_publish_evt_topic_emits_no_event() -> None:
    adapter, svc, events = _wired()
    svc.publish("evt.abc123", "event-id", b"payload")

    assert adapter.published == [("evt.abc123", "event-id", b"payload")]
    assert events.published == []


def test_enqueue_evt_topic_emits_no_event() -> None:
    adapter, svc, events = _wired()
    svc.enqueue("evt.abc123", "event-id", b"payload")

    assert adapter.enqueued == [("evt.abc123", "event-id", b"payload")]
    assert events.published == []


def test_publish_evt_topic_does_not_emit_buserror_on_failure() -> None:
    adapter, svc, events = _wired()
    adapter.publish_raises = RuntimeError("adapter down")

    with pytest.raises(RuntimeError):
        svc.publish("evt.xyz", "rk", b"x")
    # No event emitted (recursion guard applies to errors too).
    assert events.published == []


# ---------------------------------------------------------------------------
# Adapter exceptions emit BusError and re-raise.
# ---------------------------------------------------------------------------


def test_publish_failure_emits_bus_error_and_reraises() -> None:
    adapter, svc, events = _wired()
    adapter.publish_raises = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        svc.publish("topic.x", "rk", b"data")

    errors = [e for e in events.published if isinstance(e, BusError)]
    assert len(errors) == 1
    err = errors[0]
    assert err.topic == "topic.x"
    assert err.routing_key == "rk"
    assert err.operation == "publish"
    assert "boom" in (err.message or "")


def test_enqueue_failure_emits_bus_error_and_reraises() -> None:
    adapter, svc, events = _wired()
    adapter.enqueue_raises = RuntimeError("nope")

    with pytest.raises(RuntimeError):
        svc.enqueue("jobs.x", "rk", b"data")

    errors = [e for e in events.published if isinstance(e, BusError)]
    assert len(errors) == 1
    err = errors[0]
    assert err.operation == "enqueue"
    assert "nope" in (err.message or "")


# ---------------------------------------------------------------------------
# Best-effort publishing — EventService failure must not break the bus.
# ---------------------------------------------------------------------------


def test_publisher_exception_does_not_break_publish() -> None:
    class _ExplodingEvents:
        def publish(self, event):
            raise RuntimeError("event bus down")

    adapter = _FakeAdapter()
    svc = BusService(adapter)
    svc.set_services(_FakeServices(events=_ExplodingEvents()))

    # Must not raise — bus operation is authoritative.
    svc.publish("topic.x", "rk", b"hello")
    svc.enqueue("topic.x", "rk", b"hello")

    assert adapter.published == [("topic.x", "rk", b"hello")]
    assert adapter.enqueued == [("topic.x", "rk", b"hello")]

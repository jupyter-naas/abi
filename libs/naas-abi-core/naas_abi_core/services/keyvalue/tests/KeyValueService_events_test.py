# mypy: disable-error-code="arg-type,misc"
"""Tests for KeyValueService event publication."""

from __future__ import annotations

import pytest

from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.keyvalue.ontologies.modules.KeyValueEventOntology import (
    KeyValueDeleted,
    KeyValueError,
    KeyValueSet,
)


class _FakeKVAdapter(IKeyValueAdapter):
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def get(self, key: str) -> bytes:
        return self.store[key]

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self.store[key] = value

    def set_if_not_exists(
        self, key: str, value: bytes, ttl: int | None = None
    ) -> bool:
        if key in self.store:
            return False
        self.store[key] = value
        return True

    def delete(self, key: str) -> None:
        del self.store[key]

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        if self.store.get(key) != value:
            return False
        del self.store[key]
        return True

    def exists(self, key: str) -> bool:
        return key in self.store


class _BrokenKVAdapter(IKeyValueAdapter):
    def get(self, key: str) -> bytes:
        raise OSError("backend down")

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        raise OSError("backend down")

    def set_if_not_exists(
        self, key: str, value: bytes, ttl: int | None = None
    ) -> bool:
        raise OSError("backend down")

    def delete(self, key: str) -> None:
        raise OSError("backend down")

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        raise OSError("backend down")

    def exists(self, key: str) -> bool:
        raise OSError("backend down")


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


def _wired() -> tuple[KeyValueService, _FakeEventService]:
    svc = KeyValueService(_FakeKVAdapter())
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))
    return svc, events


def test_no_events_when_unwired() -> None:
    svc = KeyValueService(_FakeKVAdapter())
    svc.set(b"k".decode(), b"v")
    svc.delete("k")  # must not crash


def test_no_events_when_events_unavailable() -> None:
    svc = KeyValueService(_FakeKVAdapter())
    svc.set_services(_FakeServices(events=None))
    svc.set("k", b"v")
    svc.delete("k")  # must not crash


def test_set_emits_keyvalue_set_without_ttl() -> None:
    svc, events = _wired()
    svc.set("k", b"hello")

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, KeyValueSet)
    assert evt.key == "k"
    assert evt.size_bytes == 5
    assert evt.ttl_seconds is None


def test_set_emits_keyvalue_set_with_ttl() -> None:
    svc, events = _wired()
    svc.set("k", b"hello", ttl=30)

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, KeyValueSet)
    assert evt.ttl_seconds == 30
    assert evt.size_bytes == 5


def test_delete_emits_keyvalue_deleted() -> None:
    svc, events = _wired()
    svc.set("k", b"v")
    events.published.clear()

    svc.delete("k")

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, KeyValueDeleted)
    assert evt.key == "k"


def test_set_if_not_exists_emits_only_when_wrote() -> None:
    svc, events = _wired()

    assert svc.set_if_not_exists("k", b"v1") is True
    assert len(events.published) == 1
    assert isinstance(events.published[0], KeyValueSet)

    assert svc.set_if_not_exists("k", b"v2") is False
    # No second event for the no-op
    assert len(events.published) == 1


def test_delete_if_value_matches_emits_only_when_matched() -> None:
    svc, events = _wired()
    svc.set("k", b"v")
    events.published.clear()

    assert svc.delete_if_value_matches("k", b"other") is False
    assert events.published == []

    svc.set("k", b"v")
    events.published.clear()
    assert svc.delete_if_value_matches("k", b"v") is True
    assert len(events.published) == 1
    assert isinstance(events.published[0], KeyValueDeleted)


def test_adapter_exception_emits_error_and_reraises() -> None:
    svc = KeyValueService(_BrokenKVAdapter())
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))

    with pytest.raises(OSError):
        svc.set("k", b"v")

    errors = [e for e in events.published if isinstance(e, KeyValueError)]
    assert len(errors) == 1
    err = errors[0]
    assert err.key == "k"
    assert err.operation == "set"
    assert "backend down" in (err.message or "")

    events.published.clear()
    with pytest.raises(OSError):
        svc.delete("k")
    errors = [e for e in events.published if isinstance(e, KeyValueError)]
    assert len(errors) == 1
    assert errors[0].operation == "delete"

    events.published.clear()
    with pytest.raises(OSError):
        svc.set_if_not_exists("k", b"v")
    errors = [e for e in events.published if isinstance(e, KeyValueError)]
    assert len(errors) == 1
    assert errors[0].operation == "set_if_not_exists"

    events.published.clear()
    with pytest.raises(OSError):
        svc.delete_if_value_matches("k", b"v")
    errors = [e for e in events.published if isinstance(e, KeyValueError)]
    assert len(errors) == 1
    assert errors[0].operation == "delete_if_value_matches"


def test_publisher_exception_does_not_break_call() -> None:
    class _Exploding:
        def publish(self, event):
            raise RuntimeError("event bus down")

    svc = KeyValueService(_FakeKVAdapter())
    svc.set_services(_FakeServices(events=_Exploding()))

    svc.set("k", b"v")
    assert svc.get("k") == b"v"
    svc.delete("k")
    assert svc.exists("k") is False

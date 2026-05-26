"""Tests for ObjectStorageService — event emission on put/delete."""

from __future__ import annotations

from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.event.ontologies.modules.EventOntology import LogProcess
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ontologies.modules.ObjectStorageEventOntology import (
    ObjectDeleted,
    ObjectPut,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


def _make(tmp_path):
    storage = ObjectStorageService(
        adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path / "storage"))
    )
    events = EventService(
        adapter=EventSQLiteAdapter(str(tmp_path / "events.sqlite"))
    )
    services = IEngine.Services(object_storage=storage, events=events)
    services.wire_services()
    return storage, events


def test_put_object_publishes_object_put_event(tmp_path):
    storage, events = _make(tmp_path)

    storage.put_object("objects", "hello.txt", b"hello world")

    [evt] = events.query(event_class=ObjectPut)
    assert evt.prefix == "objects"
    assert evt.key == "hello.txt"
    assert evt.size_bytes == len(b"hello world")


def test_delete_object_publishes_object_deleted_event(tmp_path):
    storage, events = _make(tmp_path)

    storage.put_object("objects", "k.txt", b"x")
    storage.delete_object("objects", "k.txt")

    [evt] = events.query(event_class=ObjectDeleted)
    assert evt.prefix == "objects"
    assert evt.key == "k.txt"


def test_no_event_service_wired_is_safe(tmp_path):
    storage = ObjectStorageService(
        adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path / "storage"))
    )
    # No wire_services() call — services_wired is False.
    storage.put_object("objects", "k.txt", b"x")
    storage.delete_object("objects", "k.txt")


def test_event_publish_failure_does_not_break_put(tmp_path):
    storage, events = _make(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("event store down")

    events.publish = boom  # type: ignore[assignment]

    # Must not raise — storage is the source of truth.
    storage.put_object("objects", "k.txt", b"x")
    assert storage.get_object("objects", "k.txt") == b"x"


def test_event_classes_are_recognized_as_logprocess_subclasses():
    """The codegen rebases ObjectPut/ObjectDeleted on the canonical
    LogProcess; without this, the EventService subclass-index walk used by
    untyped query() would not find them."""
    assert issubclass(ObjectPut, LogProcess)
    assert issubclass(ObjectDeleted, LogProcess)

    def walk(cls):
        yield cls
        for sub in cls.__subclasses__():
            yield from walk(sub)

    names = {c.__name__ for c in walk(LogProcess)}
    assert {"ObjectPut", "ObjectDeleted"}.issubset(names)


def test_event_service_reconstructs_typed_subclass_without_hint(tmp_path):
    """Untyped events.query() must reconstruct ObjectPut as ObjectPut (not
    a bare LogProcess) and preserve its domain fields. This is the test
    that would have failed before we wired the ontology to import the
    canonical LogProcess via owl:imports."""
    storage, events = _make(tmp_path)

    storage.put_object("objects", "hello.txt", b"hello world")
    storage.delete_object("objects", "hello.txt")

    rows = sorted(events.query(), key=lambda e: e._seq)
    assert [type(r).__name__ for r in rows] == ["ObjectPut", "ObjectDeleted"]

    put_evt, del_evt = rows
    assert isinstance(put_evt, ObjectPut)
    assert put_evt.prefix == "objects"
    assert put_evt.key == "hello.txt"
    assert put_evt.size_bytes == len(b"hello world")

    assert isinstance(del_evt, ObjectDeleted)
    assert del_evt.prefix == "objects"
    assert del_evt.key == "hello.txt"


def test_event_service_round_trips_via_codec(tmp_path):
    """Publish + reload: the JSON codec must round-trip every field on the
    ontology-generated subclass."""
    storage, events = _make(tmp_path)

    storage.put_object("a", "b.bin", b"payload")

    [reloaded] = events.query()
    assert reloaded._class_uri == ObjectPut._class_uri
    assert reloaded.created_at is not None  # populated by publish()
    assert reloaded.prefix == "a"
    assert reloaded.key == "b.bin"
    assert reloaded.size_bytes == len(b"payload")

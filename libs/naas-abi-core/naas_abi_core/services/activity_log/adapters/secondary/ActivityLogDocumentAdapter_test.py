import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogDocumentAdapter import (
    NAMESPACE,
    ActivityLogDocumentAdapter,
)
from naas_abi_core.services.activity_log.tests.activity_log__secondary_adapter__generic_test import (
    GenericActivityLogSecondaryAdapterTest,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentService import DocumentService


def _postgres_root():
    dsn = os.environ.get("DOCUMENT_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set DOCUMENT_TEST_POSTGRES_DSN to run on PostgreSQL documents")
    from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL import (
        DocumentSecondaryAdapterPostgreSQL,
    )

    adapter = DocumentSecondaryAdapterPostgreSQL(
        dsn=dsn, schema="activity_log_test_" + uuid4().hex
    )
    return DocumentService._for_engine(adapter), adapter


@pytest.fixture(params=["sqlite", "postgresql"])
def root(request, tmp_path):
    """The engine's document root, as ``wire_services`` hands it over."""
    if request.param == "sqlite":
        adapter = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        root = DocumentService._for_engine(adapter)
    else:
        root, adapter = _postgres_root()
    yield root
    adapter.close()


def wired(root) -> ActivityLogDocumentAdapter:
    adapter = ActivityLogDocumentAdapter()
    adapter.wire_services(SimpleNamespace(document=root))
    return adapter


class TestActivityLogDocumentAdapter(GenericActivityLogSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return ActivityLogDocumentAdapter

    @pytest.fixture
    def adapter(self, root):
        adapter = wired(root)
        yield adapter
        adapter.shutdown()


def test_events_live_in_the_activity_log_namespace(root):
    adapter = wired(root)
    adapter.record(ActivityEvent(actor_id="user:a", event_type="x"))

    assert NAMESPACE in root.namespaces()


def test_a_restarted_engine_continues_each_actor_s_numbering(root):
    actor = f"user:{uuid4()}"
    first = wired(root)
    for _ in range(3):
        first.record(ActivityEvent(actor_id=actor, event_type="x"))

    second = wired(root)
    second.record(ActivityEvent(actor_id=actor, event_type="y"))

    assert [e.seq for e in second.query(actor)] == [1, 2, 3, 4]
    assert actor in second.list_actors()


def test_two_engines_recording_for_one_actor_lose_nothing(root):
    # As during a handover, when both engines briefly serve.
    actor = f"user:{uuid4()}"
    engines = [wired(root), wired(root)]

    def record(i: int) -> None:
        engines[i % 2].record(
            ActivityEvent(actor_id=actor, event_type="x", attributes={"i": i})
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(record, range(40)))

    events = engines[0].query(actor)
    assert sorted(e.attributes["i"] for e in events) == list(range(40))
    assert [e.seq for e in events] == list(range(1, 41))


def test_naive_timestamps_are_read_as_utc(root):
    from datetime import datetime

    adapter = wired(root)
    actor = f"user:{uuid4()}"
    adapter.record(
        ActivityEvent(
            actor_id=actor,
            event_type="x",
            timestamp=datetime(2026, 1, 2, 3, 4, 5),  # noqa: DTZ001 - naive on purpose
        )
    )

    (event,) = adapter.query(actor)
    assert event.timestamp.isoformat() == "2026-01-02T03:04:05+00:00"


def test_an_unwired_adapter_says_so():
    with pytest.raises(RuntimeError, match="not wired"):
        ActivityLogDocumentAdapter().query("user:a")


def test_the_service_wires_its_adapter(root):
    adapter = ActivityLogDocumentAdapter()
    service = ActivityLogService(adapter)

    service.set_services(SimpleNamespace(document=root))  # type: ignore[arg-type]
    service.record(ActivityEvent(actor_id="user:a", event_type="x"))

    assert len(service.query("user:a")) == 1

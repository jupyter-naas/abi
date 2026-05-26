from uuid import uuid4

import pytest
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
)
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)


@pytest.fixture
def service(tmp_path):
    adapter = ActivityLogSqliteAdapter(data_dir=str(tmp_path))
    svc = ActivityLogService(adapter=adapter)
    yield svc
    svc.shutdown()


def test_service_delegates_record_and_query(service):
    actor = f"user:{uuid4()}"
    service.record(ActivityEvent(actor_id=actor, event_type="x"))
    assert len(service.query(actor)) == 1


def test_service_delegates_list_actors(service):
    a, b = f"user:{uuid4()}", f"user:{uuid4()}"
    service.record(ActivityEvent(actor_id=a, event_type="x"))
    service.record(ActivityEvent(actor_id=b, event_type="x"))
    actors = service.list_actors()
    assert a in actors
    assert b in actors


def test_service_delegates_query_filters(service):
    actor = f"user:{uuid4()}"
    service.record(ActivityEvent(actor_id=actor, event_type="http.request"))
    service.record(ActivityEvent(actor_id=actor, event_type="other"))
    results = service.query(actor, ActivityLogQuery(event_type="http.request"))
    assert len(results) == 1


class _FailingAdapter(IActivityLogAdapter):
    def __init__(self) -> None:
        self.recorded = 0

    def record(self, event):
        self.recorded += 1
        raise RuntimeError("boom")

    def query(self, actor_id, query=None):
        return []

    def list_actors(self):
        return []

    def shutdown(self):
        pass


def test_record_swallows_adapter_failures():
    adapter = _FailingAdapter()
    service = ActivityLogService(adapter=adapter)
    # Must not raise. Activity logging must never break the call site.
    service.record(ActivityEvent(actor_id="x", event_type="y"))
    assert adapter.recorded == 1

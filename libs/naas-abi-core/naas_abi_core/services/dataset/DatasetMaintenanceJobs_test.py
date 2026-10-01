from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from naas_abi_core.module.jobs import Cron, JobContext
from naas_abi_core.services.dataset.DatasetMaintenanceJobs import (
    DATASET_JOBS_OWNER,
    DatasetMaintenanceJobs,
)
from naas_abi_core.services.dataset.DatasetPort import QueryResult
from naas_abi_core.services.dataset.DatasetService import DatasetService


def _service():
    service = Mock(spec=DatasetService)
    service.list.side_effect = lambda namespace=None: [
        SimpleNamespace(name=name, namespace=scope)
        for name, scope in [("a", "first"), ("b", "second")]
        if namespace is None or scope == namespace
    ]
    service.describe.side_effect = lambda name, namespace: SimpleNamespace(
        name=name, namespace=namespace
    )
    service.flush.return_value = QueryResult(columns=["rows"], rows=[{"rows": 3}])
    service.compact.return_value = QueryResult(columns=["files"], rows=[{"files": 1}])
    service.check_catalog_pressure.return_value = 7
    return service


def _ctx(payload=None):
    return JobContext("run-1", "job", 1, {"kind": "manual"}, payload or {})


def test_schedules_match_the_dagster_ones_in_utc():
    jobs = {j.name: j for j in DatasetMaintenanceJobs.jobs}

    assert DATASET_JOBS_OWNER == "naas_abi_core.dataset"
    assert jobs["dataset_compaction"].triggers == (
        Cron("0 0 2 * * *", time_zone="UTC"),
    )
    assert jobs["dataset_catalog_monitor"].triggers == (
        Cron("0 0 * * * *", time_zone="UTC"),
    )
    assert DatasetMaintenanceJobs(_service()).missing_job_handlers() == set()


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({}, [("a", "first"), ("b", "second")]),
        ({"namespace": "first"}, [("a", "first")]),
        ({"name": "a", "namespace": "first"}, [("a", "first")]),
        ({"name": "a"}, [("a", "default")]),
    ],
)
def test_compaction_flushes_then_compacts_the_targeted_datasets(payload, expected):
    service = _service()
    ctx = _ctx(payload)

    result = DatasetMaintenanceJobs(service).compact(ctx)

    assert result == {"datasets_processed": len(expected)}
    operations = [c for c in service.mock_calls if c[0] in ("flush", "compact")]
    assert operations == [
        op
        for name, namespace in expected
        for op in (
            call.flush(name, namespace=namespace),
            call.compact(name, namespace=namespace),
        )
    ]
    assert len(ctx.logs) == 2 * len(expected)


def test_failed_flush_prevents_compaction():
    service = _service()
    service.flush.side_effect = RuntimeError("flush failed")

    with pytest.raises(RuntimeError, match="flush failed"):
        DatasetMaintenanceJobs(service).compact(_ctx({"name": "a"}))
    service.compact.assert_not_called()


def test_cancelled_compaction_stops_between_datasets():
    service = _service()
    ctx = _ctx()
    ctx.cancelled.set()

    assert DatasetMaintenanceJobs(service).compact(ctx) == {"datasets_processed": 0}
    service.flush.assert_not_called()


def test_catalog_monitor_reports_unflushed_records():
    service = _service()
    ctx = _ctx({"inline_warning_threshold": 10})

    result = DatasetMaintenanceJobs(service).monitor_catalogs(ctx)

    assert result == {"first.a": 7, "second.b": 7}
    service.check_catalog_pressure.assert_any_call(
        "a", namespace="first", threshold_records=10
    )

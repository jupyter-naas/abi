import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest
from dagster import DefaultScheduleStatus, Definitions, job

from naas_abi_core.apps.dagster.DatasetCompaction import dataset_compaction_definitions
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_core.services.dataset.DatasetPort import QueryResult
from naas_abi_core.services.dataset.DatasetService import DatasetService


@pytest.mark.parametrize(
    "config, expected",
    [
        ({}, [("a", "first"), ("b", "second")]),
        ({"namespace": "first"}, [("a", "first")]),
        ({"name": "a", "namespace": "first"}, [("a", "first")]),
        ({"name": "a"}, [("a", "default")]),
    ],
)
def test_job_targets_datasets(config, expected):
    service = Mock(spec=DatasetService)
    service.list.side_effect = lambda namespace: [
        SimpleNamespace(name=name, namespace=scope)
        for name, scope in [("a", "first"), ("b", "second")]
        if namespace is None or scope == namespace
    ]
    service.describe.side_effect = lambda name, namespace: SimpleNamespace(
        name=name, namespace=namespace
    )
    service.compact.return_value = QueryResult(columns=[], rows=[])
    definitions = dataset_compaction_definitions(service)
    Definitions.validate_loadable(definitions)
    result = definitions.get_job_def("dataset_compaction_job").execute_in_process(
        run_config={"ops": {"compact_datasets": {"config": config}}}
    )
    assert result.success
    assert [
        (call.args[0], call.kwargs["namespace"])
        for call in service.compact.call_args_list
    ] == expected
    schedule = definitions.get_schedule_def("dataset_compaction_daily")
    assert schedule.default_status == DefaultScheduleStatus.RUNNING
    assert schedule.cron_schedule == "0 2 * * *"
    assert schedule.execution_timezone == "UTC"
    operations = [c for c in service.mock_calls if c[0] in ("flush", "compact")]
    assert operations == [
        operation
        for name, namespace in expected
        for operation in (
            call.flush(name, namespace=namespace),
            call.compact(name, namespace=namespace),
        )
    ]


def test_empty_catalog_and_failed_compaction():
    service = Mock(spec=DatasetService)
    service.list.return_value = []
    job = dataset_compaction_definitions(service).get_job_def("dataset_compaction_job")
    assert job.execute_in_process().success
    service.compact.assert_not_called()
    service.list.return_value = [SimpleNamespace(name="a", namespace="first")]
    service.compact.side_effect = RuntimeError("compaction failed")
    assert not job.execute_in_process(raise_on_error=False).success


def test_failed_flush_prevents_compaction():
    service = Mock(spec=DatasetService)
    service.list.return_value = [SimpleNamespace(name="events", namespace="analytics")]
    service.flush.side_effect = RuntimeError("flush failed")
    job = dataset_compaction_definitions(service).get_job_def("dataset_compaction_job")
    assert not job.execute_in_process(raise_on_error=False).success
    service.compact.assert_not_called()


def test_catalog_monitor_only_checks_pressure():
    service = Mock(spec=DatasetService)
    service.list.return_value = [SimpleNamespace(name="events", namespace="analytics")]
    definitions = dataset_compaction_definitions(service)
    result = definitions.get_job_def("dataset_catalog_monitor_job").execute_in_process(
        run_config={
            "ops": {
                "check_dataset_catalogs": {"config": {"inline_warning_threshold": 2000}}
            }
        }
    )
    assert result.success
    service.check_catalog_pressure.assert_called_once_with(
        "events", namespace="analytics", threshold_records=2000
    )
    service.flush.assert_not_called()
    service.compact.assert_not_called()
    schedule = definitions.get_schedule_def("dataset_catalog_monitor_hourly")
    assert schedule.default_status == DefaultScheduleStatus.RUNNING
    assert schedule.cron_schedule == "0 * * * *"


@pytest.mark.parametrize("available", [True, False])
def test_app_registers_maintenance_alongside_module_jobs(monkeypatch, available):
    @job
    def module_job():
        pass

    class ModuleOrchestration(DagsterOrchestration):
        @classmethod
        def New(cls):
            return cls(Definitions(jobs=[module_job]))

    engine = SimpleNamespace(
        load=Mock(),
        services=SimpleNamespace(
            dataset_available=lambda: available, dataset=Mock(spec=DatasetService)
        ),
        modules={"example": SimpleNamespace(orchestrations=[ModuleOrchestration])},
    )
    engine_module = ModuleType("naas_abi_core.engine.Engine")
    engine_module.Engine = lambda: engine
    monkeypatch.setitem(sys.modules, "naas_abi_core.engine.Engine", engine_module)
    definitions = runpy.run_path(str(Path(__file__).with_name("dagster.py")))[
        "definitions"
    ]
    Definitions.validate_loadable(definitions)
    assert definitions.get_job_def("module_job").name == "module_job"
    names = {definition.name for definition in definitions.jobs}
    assert ("dataset_compaction_job" in names) is available
    engine.load.assert_called_once()

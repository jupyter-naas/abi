"""Tests for XDatasetCompactionOrchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dagster as dg
from naas_abi_marketplace.applications.x.orchestrations.XDatasetCompactionOrchestration import (
    _CRON,
    _JOB_NAME,
    _SCHEDULE_NAME,
    XDatasetCompactionOrchestration,
    _run_compaction,
)


def test_schedule_runs_off_the_hour_and_defaults_running():
    orch = XDatasetCompactionOrchestration.New()
    schedule = {s.name: s for s in orch.definitions.schedules or []}[_SCHEDULE_NAME]
    assert schedule.cron_schedule == _CRON == "30 */6 * * *"
    assert schedule.default_status == dg.DefaultScheduleStatus.RUNNING
    assert {j.name for j in orch.definitions.jobs or []} == {_JOB_NAME}


def test_schedule_skips_while_a_compaction_is_running():
    orch = XDatasetCompactionOrchestration.New()
    schedule = {s.name: s for s in orch.definitions.schedules or []}[_SCHEDULE_NAME]
    context = MagicMock(spec=dg.ScheduleEvaluationContext)
    context.instance.get_runs.return_value = []
    assert isinstance(schedule(context), dg.RunRequest)
    context.instance.get_runs.return_value = [MagicMock()]
    assert isinstance(schedule(context), dg.SkipReason)


def test_run_compaction_skips_when_dataset_sync_is_disabled():
    module = MagicMock(name="x_module")
    with (
        patch(
            "naas_abi_marketplace.applications.x.ABIModule.get_instance",
            return_value=module,
        ),
        patch(
            "naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store.x_dataset_sync_enabled",
            return_value=False,
        ),
        patch(
            "naas_abi_marketplace.applications.x.apps.x_proxy.dataset.maintenance.compact_x_datasets"
        ) as compact,
    ):
        assert _run_compaction() == {"skipped": "dataset sync disabled"}
    compact.assert_not_called()


def test_run_compaction_compacts_the_module_dataset():
    module = MagicMock(name="x_module")
    with (
        patch(
            "naas_abi_marketplace.applications.x.ABIModule.get_instance",
            return_value=module,
        ),
        patch(
            "naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store.x_dataset_sync_enabled",
            return_value=True,
        ),
        patch(
            "naas_abi_marketplace.applications.x.apps.x_proxy.dataset.maintenance.compact_x_datasets",
            return_value={"files": {}},
        ) as compact,
    ):
        assert _run_compaction() == {"files": {}}
    compact.assert_called_once_with(module.engine.services.dataset)

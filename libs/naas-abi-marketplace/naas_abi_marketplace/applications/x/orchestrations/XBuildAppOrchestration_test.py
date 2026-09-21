"""Tests for XBuildAppOrchestration default trigger status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dagster as dg
from naas_abi_marketplace.applications.x.orchestrations.XBuildAppOrchestration import (
    _MEDIA_OP_NAME,
    _OP_NAME,
    _SCHEDULE_NAME,
    XBuildAppOrchestration,
    _run_build_cycle,
    _run_media_batch,
)


def test_hourly_schedule_defaults_running():
    orch = XBuildAppOrchestration.New()

    schedule_by_name = {s.name: s for s in orch.definitions.schedules or []}
    schedule = schedule_by_name[_SCHEDULE_NAME]

    assert schedule.cron_schedule == "0 * * * *"
    assert schedule.default_status == dg.DefaultScheduleStatus.RUNNING


def test_definitions_include_build_job_and_running_schedule():
    orch = XBuildAppOrchestration.New()

    job_names = {j.name for j in orch.definitions.jobs or []}
    assert "x_build_app_x_proxy" in job_names
    assert len(list(orch.definitions.schedules or [])) == 1
    assert len(list(orch.definitions.sensors or [])) == 0


def test_build_job_chains_media_worker_after_build():
    orch = XBuildAppOrchestration.New()
    job = next(j for j in orch.definitions.jobs or [] if j.name == "x_build_app_x_proxy")
    op_names = {node.name for node in job.nodes}
    assert op_names == {_OP_NAME, _MEDIA_OP_NAME}


def test_run_build_cycle_resolves_abi_module():
    """Regression: the op looks up ABIModule at runtime, not only at New()."""
    module = MagicMock(name="x_module")

    with (
        patch(
            "naas_abi_marketplace.applications.x.ABIModule.get_instance",
            return_value=module,
        ) as get_instance,
        patch(
            "naas_abi_marketplace.applications.x.orchestrations.utils.publish_x_app",
            return_value={"ok": True},
        ) as publish,
        patch(
            "naas_abi_marketplace.applications.x.orchestrations.utils.refresh_x_cache",
            return_value={"rebuilt": True},
        ) as refresh,
    ):
        summary = _run_build_cycle(full_users=True, rebuild_projection=True)

    get_instance.assert_called_once_with()
    refresh.assert_called_once_with(module, full=True)
    publish.assert_called_once_with(module, full_users=True, direct_user_limit=100)
    assert summary == {
        "projection_rebuild": {"rebuilt": True},
        "app": {"ok": True},
    }


def test_run_media_batch_resolves_abi_module():
    module = MagicMock(name="x_module")
    module.configuration.app.dataset.media_batch_size = 8

    with (
        patch(
            "naas_abi_marketplace.applications.x.ABIModule.get_instance",
            return_value=module,
        ) as get_instance,
        patch(
            "naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_worker.process_pending_media_batch",
            return_value={"processed": 2},
        ) as process,
    ):
        result = _run_media_batch()

    get_instance.assert_called_once_with()
    process.assert_called_once_with(module, limit=8)
    assert result == {"processed": 2}

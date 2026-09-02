"""Tests for XBuildAppOrchestration default trigger status."""

from __future__ import annotations

import dagster as dg
from naas_abi_marketplace.applications.x.orchestrations.XBuildAppOrchestration import (
    _SCHEDULE_NAME,
    XBuildAppOrchestration,
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

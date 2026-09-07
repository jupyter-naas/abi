"""Tests for XSearchWorkflowOrchestration default trigger status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dagster as dg
from naas_abi_marketplace.applications.x import XTweetSearchWorkflowConfiguration
from naas_abi_marketplace.applications.x.orchestrations.XSearchWorkflowOrchestration import (
    XSearchWorkflowOrchestration,
    _build_search_workflow_definitions,
)

_QUERY = "(drone OR drones OR UAS OR UAV) lang:en -is:retweet"


def _workflow_config(
    name: str = "drones_and_uas", **overrides
) -> XTweetSearchWorkflowConfiguration:
    return XTweetSearchWorkflowConfiguration(
        name=name,
        query=_QUERY,
        **overrides,
    )


def test_cron_schedule_defaults_running():
    job, sensor, schedule = _build_search_workflow_definitions(
        _workflow_config(cron="10,25,40,55 * * * *")
    )

    assert job.name == "x_search_workflow_drones_and_uas"
    assert sensor is None
    assert schedule is not None
    assert schedule.name == "x_search_workflow_schedule_drones_and_uas"
    assert schedule.cron_schedule == "10,25,40,55 * * * *"
    assert schedule.default_status == dg.DefaultScheduleStatus.RUNNING


def test_interval_sensor_defaults_running():
    job, sensor, schedule = _build_search_workflow_definitions(
        _workflow_config(interval_seconds=3600)
    )

    assert job.name == "x_search_workflow_drones_and_uas"
    assert schedule is None
    assert sensor is not None
    assert sensor.name == "x_search_workflow_sensor_drones_and_uas"
    assert sensor.minimum_interval_seconds == 3600
    assert sensor.default_status == dg.DefaultSensorStatus.RUNNING


def test_definitions_expose_running_triggers_for_configured_workflows():
    cron_cfg = _workflow_config(cron="0 * * * *")
    sensor_cfg = _workflow_config(name="ai_llms", interval_seconds=1800)
    module = MagicMock()
    module.configuration.search_recent_tweets_workflow = [cron_cfg, sensor_cfg]

    with patch(
        "naas_abi_marketplace.applications.x.orchestrations."
        "XSearchWorkflowOrchestration.ABIModule.get_instance",
        return_value=module,
    ):
        orch = XSearchWorkflowOrchestration.New()

    defs = orch.definitions
    schedule_by_name = {s.name: s for s in defs.schedules or []}
    sensor_by_name = {s.name: s for s in defs.sensors or []}

    assert (
        schedule_by_name["x_search_workflow_schedule_drones_and_uas"].default_status
        == dg.DefaultScheduleStatus.RUNNING
    )
    assert (
        sensor_by_name["x_search_workflow_sensor_ai_llms"].default_status
        == dg.DefaultSensorStatus.RUNNING
    )


def test_definitions_skip_duplicate_workflow_names():
    duplicate = _workflow_config(cron="0 * * * *")
    module = MagicMock()
    module.configuration.search_recent_tweets_workflow = [duplicate, duplicate]

    with patch(
        "naas_abi_marketplace.applications.x.orchestrations."
        "XSearchWorkflowOrchestration.ABIModule.get_instance",
        return_value=module,
    ):
        orch = XSearchWorkflowOrchestration.New()

    assert len(list(orch.definitions.schedules or [])) == 1

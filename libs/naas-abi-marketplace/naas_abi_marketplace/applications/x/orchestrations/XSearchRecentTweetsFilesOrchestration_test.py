"""Tests for XSearchRecentTweetsFilesOrchestration default trigger status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dagster as dg
from naas_abi_marketplace.applications.x import XSearchRecentTweetsFilesConfiguration
from naas_abi_marketplace.applications.x.orchestrations.XSearchRecentTweetsFilesOrchestration import (
    XSearchRecentTweetsFilesOrchestration,
    _build_reprocess_files_definitions,
)


def _files_config(name: str = "reprocess_envelopes", **overrides):
    return XSearchRecentTweetsFilesConfiguration(name=name, **overrides)


def test_cron_schedule_defaults_running_when_enabled_false():
    job, sensor, schedule = _build_reprocess_files_definitions(
        _files_config(cron="0,15,30,45 * * * *", enabled=False)
    )

    assert job.name == "x_search_recent_tweets_files_reprocess_envelopes"
    assert sensor is None
    assert schedule is not None
    assert schedule.name == "x_search_recent_tweets_files_schedule_reprocess_envelopes"
    assert schedule.default_status == dg.DefaultScheduleStatus.RUNNING


def test_interval_sensor_defaults_running_when_enabled_false():
    job, sensor, schedule = _build_reprocess_files_definitions(
        _files_config(interval_seconds=3600, enabled=False)
    )

    assert job.name == "x_search_recent_tweets_files_reprocess_envelopes"
    assert schedule is None
    assert sensor is not None
    assert sensor.name == "x_search_recent_tweets_files_sensor_reprocess_envelopes"
    assert sensor.default_status == dg.DefaultSensorStatus.RUNNING


def test_definitions_expose_running_triggers_for_configured_entries():
    cron_cfg = _files_config(cron="0 * * * *", enabled=False)
    sensor_cfg = _files_config(name="hourly_sweep", interval_seconds=1800)
    module = MagicMock()
    module.configuration.search_recent_tweets_files = [cron_cfg, sensor_cfg]

    with patch(
        "naas_abi_marketplace.applications.x.orchestrations."
        "XSearchRecentTweetsFilesOrchestration.ABIModule.get_instance",
        return_value=module,
    ):
        orch = XSearchRecentTweetsFilesOrchestration.New()

    schedule_by_name = {s.name: s for s in orch.definitions.schedules or []}
    sensor_by_name = {s.name: s for s in orch.definitions.sensors or []}

    assert (
        schedule_by_name[
            "x_search_recent_tweets_files_schedule_reprocess_envelopes"
        ].default_status
        == dg.DefaultScheduleStatus.RUNNING
    )
    assert (
        sensor_by_name["x_search_recent_tweets_files_sensor_hourly_sweep"].default_status
        == dg.DefaultSensorStatus.RUNNING
    )


def test_definitions_skip_duplicate_files_names():
    duplicate = _files_config(cron="0 * * * *")
    module = MagicMock()
    module.configuration.search_recent_tweets_files = [duplicate, duplicate]

    with patch(
        "naas_abi_marketplace.applications.x.orchestrations."
        "XSearchRecentTweetsFilesOrchestration.ABIModule.get_instance",
        return_value=module,
    ):
        orch = XSearchRecentTweetsFilesOrchestration.New()

    assert len(list(orch.definitions.schedules or [])) == 1

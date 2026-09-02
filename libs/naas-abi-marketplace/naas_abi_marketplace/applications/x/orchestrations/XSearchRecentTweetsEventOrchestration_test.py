"""Tests for XSearchRecentTweetsEventOrchestration default trigger status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dagster as dg
from naas_abi_marketplace.applications.x import XSearchRecentTweetsEventConfiguration
from naas_abi_marketplace.applications.x.orchestrations.XSearchRecentTweetsEventOrchestration import (
    XSearchRecentTweetsEventOrchestration,
    _build_search_recent_tweets_event_sensor,
)


def _event_config(
    name: str = "search_envelopes", **overrides
) -> XSearchRecentTweetsEventConfiguration:
    return XSearchRecentTweetsEventConfiguration(name=name, **overrides)


def test_object_put_sensor_defaults_running_when_enabled_false():
    job, sensor = _build_search_recent_tweets_event_sensor(
        _event_config(enabled=False)
    )

    assert job.name == "x_search_recent_tweets_events_search_envelopes"
    assert sensor.name == "x_search_recent_tweets_put_sensor_search_envelopes"
    assert sensor.default_status == dg.DefaultSensorStatus.RUNNING


def test_definitions_expose_running_sensors_for_configured_entries():
    cfg_a = _event_config(name="search_envelopes", enabled=False)
    cfg_b = _event_config(name="ai_llms", prefix="x/search_recent_tweets/ai_llms")
    module = MagicMock()
    module.configuration.search_recent_tweets_event = [cfg_a, cfg_b]

    with patch(
        "naas_abi_marketplace.applications.x.orchestrations."
        "XSearchRecentTweetsEventOrchestration.ABIModule.get_instance",
        return_value=module,
    ):
        orch = XSearchRecentTweetsEventOrchestration.New()

    sensor_by_name = {s.name: s for s in orch.definitions.sensors or []}

    assert (
        sensor_by_name["x_search_recent_tweets_put_sensor_search_envelopes"].default_status
        == dg.DefaultSensorStatus.RUNNING
    )
    assert (
        sensor_by_name["x_search_recent_tweets_put_sensor_ai_llms"].default_status
        == dg.DefaultSensorStatus.RUNNING
    )


def test_definitions_skip_duplicate_event_names():
    duplicate = _event_config()
    module = MagicMock()
    module.configuration.search_recent_tweets_event = [duplicate, duplicate]

    with patch(
        "naas_abi_marketplace.applications.x.orchestrations."
        "XSearchRecentTweetsEventOrchestration.ABIModule.get_instance",
        return_value=module,
    ):
        orch = XSearchRecentTweetsEventOrchestration.New()

    assert len(list(orch.definitions.sensors or [])) == 1

"""Tests for XSearchRecentTweetsFilesOrchestration default trigger status."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import dagster as dg
import pytest
from naas_abi_marketplace.applications.x import XSearchRecentTweetsFilesConfiguration
from naas_abi_marketplace.applications.x.orchestrations.XSearchRecentTweetsFilesOrchestration import (
    OrchestrationTimeoutError,
    XSearchRecentTweetsFilesOrchestration,
    _build_reprocess_files_definitions,
    _filter_dir_envelopes_by_cutoff,
    _list_envelope_paths,
    _reprocess_files,
    _reprocess_log,
    _with_signal_timeout,
)


def _files_config(name: str = "reprocess_envelopes", **overrides):
    return XSearchRecentTweetsFilesConfiguration(name=name, **overrides)


def test_cron_schedule_defaults_running_when_enabled_false():
    job, sensor, schedule = _build_reprocess_files_definitions(
        _files_config(cron="0,15,30,45 * * * *", enabled=False)
    )

    assert job.name == "x_reprocess_recent_tweets_files_reprocess_envelopes"
    assert sensor is None
    assert schedule is not None
    assert (
        schedule.name == "x_reprocess_recent_tweets_files_schedule_reprocess_envelopes"
    )
    assert schedule.default_status == dg.DefaultScheduleStatus.RUNNING


def test_interval_sensor_defaults_running_when_enabled_false():
    job, sensor, schedule = _build_reprocess_files_definitions(
        _files_config(interval_seconds=3600, enabled=False)
    )

    assert job.name == "x_reprocess_recent_tweets_files_reprocess_envelopes"
    assert schedule is None
    assert sensor is not None
    assert sensor.name == "x_reprocess_recent_tweets_files_sensor_reprocess_envelopes"
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
            "x_reprocess_recent_tweets_files_schedule_reprocess_envelopes"
        ].default_status
        == dg.DefaultScheduleStatus.RUNNING
    )
    assert (
        sensor_by_name[
            "x_reprocess_recent_tweets_files_sensor_hourly_sweep"
        ].default_status
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


def test_reprocess_log_includes_run_id_and_phase():
    lines: list[str] = []

    _reprocess_log(
        lines.append,
        config_name="reprocess_envelopes",
        run_id="run-test",
        phase="list_envelopes",
        message="started prefix='x/search_recent_tweets'",
    )

    assert len(lines) == 1
    assert "run_id=run-test" in lines[0]
    assert "phase=list_envelopes" in lines[0]
    assert "reprocess_envelopes" in lines[0]


def test_reprocess_emits_phase_logs_for_each_stage():
    cfg = _files_config(skip_existing=True, max_age_hours=24)
    path_graph_only = (
        "x/search_recent_tweets/slug/2026-09-22T10:00:00+00:00_slug.json"
    )
    path_needs_map = "x/search_recent_tweets/slug/2026-09-22T11:00:00+00:00_slug.json"
    dagster_lines: list[str] = []

    module = MagicMock()
    module.configuration.graph_name = "http://ontology.naas.ai/graph/x"
    module.configuration.ontology_namespace = "http://ontology.naas.ai/x/"

    with (
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.ABIModule.get_instance",
            return_value=module,
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration._list_envelope_paths",
            return_value=([path_graph_only, path_needs_map], 3),
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration._mapped_file_paths",
            return_value={path_graph_only},
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.envelope_paths_in_dataset",
            return_value=set(),
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.run_search_pipeline_for_file",
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.sync_x_dataset_paths_batched",
            return_value={"batches": 1},
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.republish_x_app_after_pipeline",
            return_value={"skipped": True},
        ),
    ):
        _reprocess_files(
            cfg,
            run_id="run-phase-test",
            log=dagster_lines.append,
        )

    joined = "\n".join(dagster_lines)
    for phase in (
        "run",
        "list_envelopes",
        "mapped_paths_query",
        "dataset_projection_probe",
        "plan",
        "map_envelopes",
        "dataset_sync",
        "app_publish",
    ):
        assert f"phase={phase}" in joined
    assert "run_id=run-phase-test" in joined
    assert "elapsed=" in joined


def test_reprocess_syncs_dataset_only_when_graph_mapped_but_not_envelopes_v1():
    cfg = _files_config(skip_existing=True, max_age_hours=24)
    path_graph_only = (
        "x/search_recent_tweets/slug/2026-09-22T10:00:00+00:00_slug.json"
    )
    path_needs_map = "x/search_recent_tweets/slug/2026-09-22T11:00:00+00:00_slug.json"

    module = MagicMock()
    module.configuration.graph_name = "http://ontology.naas.ai/graph/x"
    module.configuration.ontology_namespace = "http://ontology.naas.ai/x/"

    with (
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.ABIModule.get_instance",
            return_value=module,
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration._list_envelope_paths",
            return_value=([path_graph_only, path_needs_map], 0),
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration._mapped_file_paths",
            return_value={path_graph_only},
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.envelope_paths_in_dataset",
            return_value=set(),
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.run_search_pipeline_for_file",
        ) as map_file,
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.sync_x_dataset_paths_batched",
            return_value={"batches": 1},
        ) as sync_batch,
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.republish_x_app_after_pipeline",
            return_value={},
        ),
    ):
        summary = _reprocess_files(cfg)

    map_file.assert_called_once_with(
        path_needs_map,
        persist=cfg.persist,
        graph_name=module.configuration.graph_name,
    )
    sync_batch.assert_called_once()
    synced_paths = sync_batch.call_args[0][1]
    assert path_graph_only in synced_paths
    assert path_needs_map in synced_paths
    assert summary["dataset_only"] == 1
    assert summary["processed"] == 1


def test_signal_timeout_interrupts_overlong_reprocessing():
    with pytest.raises(OrchestrationTimeoutError, match="exceeded 0.05s"):
        _with_signal_timeout(
            timeout_seconds=0.05,
            run_id="test-run",
            fn=lambda: time.sleep(0.2),
        )


def test_filter_dir_envelopes_by_cutoff_stops_after_newest_in_window_run():
    cutoff = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    recent = "x/search_recent_tweets/slug/2026-09-22T13:00:00+00:00_slug.json"
    older = "x/search_recent_tweets/slug/2026-09-22T10:00:00+00:00_slug.json"
    legacy = "x/search_recent_tweets/slug/2026-06-29T17_58_45.974146+00_00_slug.json"

    kept, skipped = _filter_dir_envelopes_by_cutoff([older, recent, legacy], cutoff)

    assert kept == [recent]
    assert skipped == 2


def test_list_envelope_paths_with_cutoff_uses_per_slug_listing():
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    recent = (
        "x/search_recent_tweets/query_slug/"
        "2026-09-23T10:00:00+00:00_query_slug.json"
    )
    old = (
        "x/search_recent_tweets/query_slug/"
        "2026-09-01T10:00:00+00:00_query_slug.json"
    )
    storage = MagicMock()
    storage.list_objects.side_effect = lambda prefix: {
        "x/search_recent_tweets": ["x/search_recent_tweets/query_slug"],
        "x/search_recent_tweets/query_slug": [recent, old],
    }.get(prefix.rstrip("/"), [])

    paths, skipped_age = _list_envelope_paths(
        storage, "x/search_recent_tweets", cutoff=cutoff
    )

    assert paths == [recent]
    assert skipped_age == 1
    assert storage.list_objects.call_count == 2


def test_reprocess_uses_bulk_dataset_lookup():
    cfg = _files_config(skip_existing=True, max_age_hours=24)
    path_graph_only = (
        "x/search_recent_tweets/slug/2026-09-22T10:00:00+00:00_slug.json"
    )
    path_needs_map = "x/search_recent_tweets/slug/2026-09-22T11:00:00+00:00_slug.json"

    module = MagicMock()
    module.configuration.graph_name = "http://ontology.naas.ai/graph/x"
    module.configuration.ontology_namespace = "http://ontology.naas.ai/x/"

    with (
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.ABIModule.get_instance",
            return_value=module,
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration._list_envelope_paths",
            return_value=([path_graph_only, path_needs_map], 0),
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration._mapped_file_paths",
            return_value={path_graph_only},
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.envelope_paths_in_dataset",
            return_value={path_graph_only},
        ) as bulk_lookup,
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.run_search_pipeline_for_file",
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.sync_x_dataset_paths_batched",
            return_value={"batches": 1},
        ),
        patch(
            "naas_abi_marketplace.applications.x.orchestrations."
            "XSearchRecentTweetsFilesOrchestration.republish_x_app_after_pipeline",
            return_value={},
        ),
    ):
        summary = _reprocess_files(cfg)

    bulk_lookup.assert_called_once_with(module, [path_graph_only, path_needs_map])
    assert summary["dataset_only"] == 0
    assert summary["skipped"] == 1
    assert summary["processed"] == 1

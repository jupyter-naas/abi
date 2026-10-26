"""Helpers shared across the X orchestrations.

Extracted from the former monolithic ``XOrchestration`` so each orchestration
file (search-workflow, event-driven, files-reprocess) can import the same
run-gating / pipeline-driving logic from a single site.

What the orchestrations do with the graph, the envelopes and the app lives in
:mod:`naas_abi_marketplace.applications.x.flows.common`, which the durable NATS
flows call as well and which imports no Dagster; it is re-exported here so the
orchestrations keep one import site. Only what needs Dagster (run statuses, the
sensor and schedule contexts) is defined in this file.
"""

from __future__ import annotations

import dagster as dg
from naas_abi_marketplace.applications.x.flows.common import (  # noqa: F401
    _COUNT_GRAPH_NAME,
    _UNSET,
    envelope_paths_in_dataset,
    followed_count_entries,
    launchpad_override,
    normalize_envelope_path,
    publish_x_app,
    republish_x_app_after_pipeline,
    run_count_for_query,
    run_search_and_map_for_query,
    run_search_pipeline_for_file,
    run_search_workflow_for_filter,
    safe_name,
    search_envelope_fully_projected,
    search_envelope_in_dataset,
    search_envelope_ingested,
    sync_x_dataset_paths,
    sync_x_dataset_paths_batched,
    x_app_publish_enabled,
)

# Dagster run statuses that mean "a run is still pending or in flight". Used to
# skip a sensor tick when a previous run for the same job hasn't finished.
IN_PROGRESS_RUN_STATUSES = [
    dg.DagsterRunStatus.QUEUED,
    dg.DagsterRunStatus.NOT_STARTED,
    dg.DagsterRunStatus.STARTING,
    dg.DagsterRunStatus.STARTED,
]


def has_in_progress_run(
    context: dg.SensorEvaluationContext | dg.ScheduleEvaluationContext,
    job_name: str,
) -> bool:
    """True iff a run for *job_name* is still queued/starting/running."""
    return count_in_progress_runs(context, job_name, limit=1) > 0


def count_in_progress_runs(
    context: dg.SensorEvaluationContext | dg.ScheduleEvaluationContext,
    job_name: str,
    *,
    limit: int | None = None,
) -> int:
    """How many runs for *job_name* are still queued/starting/running.

    Pass *limit* to short-circuit once enough in-flight runs are found (e.g.
    stop after ``max_concurrent_runs`` when only checking capacity).
    Accepts either evaluation context — both expose ``.instance``.
    """
    runs = context.instance.get_runs(
        filters=dg.RunsFilter(
            job_name=job_name,
            statuses=IN_PROGRESS_RUN_STATUSES,
        ),
        limit=limit,
    )
    return len(runs)


def report_jobs_in_progress(context) -> bool:
    """True when a daily report pipeline run is still in flight (defer dataset sync)."""
    try:
        instance = context.instance
    except AttributeError:
        return False
    runs = instance.get_runs(
        filters=dg.RunsFilter(
            statuses=IN_PROGRESS_RUN_STATUSES,
        ),
        limit=50,
    )
    for run in runs:
        name = str(getattr(run, "job_name", "") or "")
        if name.startswith("report_"):
            return True
    return False

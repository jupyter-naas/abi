"""Helpers shared across the X orchestrations.

Extracted from the former monolithic ``XOrchestration`` so each orchestration
file (search-workflow, event-driven, files-reprocess) can import the same
run-gating / pipeline-driving logic from a single site.
"""

from __future__ import annotations

import re

import dagster as dg
from naas_abi_core import logger
from naas_abi_marketplace.applications.x import ABIModule
from rdflib import URIRef

# Dedicated named graph for the recent-posts count triples (mirrors
# XCountRecentTweetsPipeline). Kept here so the count helpers below stay in one
# place shared by the count schedule and the search orchestration's count opt-in.
_COUNT_GRAPH_NAME = "http://ontology.naas.ai/graph/x_recent_posts_count"

# Dagster run statuses that mean "a run is still pending or in flight". Used to
# skip a sensor tick when a previous run for the same job hasn't finished.
IN_PROGRESS_RUN_STATUSES = [
    dg.DagsterRunStatus.QUEUED,
    dg.DagsterRunStatus.NOT_STARTED,
    dg.DagsterRunStatus.STARTING,
    dg.DagsterRunStatus.STARTED,
]


def safe_name(value: str) -> str:
    """Sanitize *value* into a Dagster-safe job/op/sensor name fragment."""
    return re.sub(r"[^a-zA-Z0-9]", "_", value) or "filter"


def launchpad_override(op_cfg: dict, key: str, default_value):
    """Return launchpad value when explicitly set, else the ABI default."""
    if key not in op_cfg:
        return default_value
    value = op_cfg[key]
    if value is None and default_value is not None:
        return default_value
    return value


def has_in_progress_run(context: dg.SensorEvaluationContext, job_name: str) -> bool:
    """True iff a run for *job_name* is still queued/starting/running."""
    return count_in_progress_runs(context, job_name, limit=1) > 0


def count_in_progress_runs(
    context: dg.SensorEvaluationContext,
    job_name: str,
    *,
    limit: int | None = None,
) -> int:
    """How many runs for *job_name* are still queued/starting/running.

    Pass *limit* to short-circuit once enough in-flight runs are found (e.g.
    stop after ``max_concurrent_runs`` when only checking capacity).
    """
    runs = context.instance.get_runs(
        filters=dg.RunsFilter(
            job_name=job_name,
            statuses=IN_PROGRESS_RUN_STATUSES,
        ),
        limit=limit,
    )
    return len(runs)


def run_search_pipeline_for_file(
    file_path: str,
    *,
    persist: bool | None = None,
    graph_name: str | None = None,
) -> None:
    """Map a persisted search_recent_tweets envelope into the graph.

    Runs :class:`XSearchRecentTweetsPipeline` in its ``file_path`` mode: it
    reads ``{query, options, results, started_at, ended_at}`` from *file_path*
    (relative to the object-storage root) instead of calling the X API, so the
    full SearchQuery / SearchResultSet / SearchRecentTweets structure is built
    from the same envelope that XSearchRecentTweetsWorkflow just wrote.
    Idempotent — the pipeline's label-based dedupe makes a re-run on the same
    file a no-op.
    """
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.x.pipelines.XSearchRecentTweetsPipeline import (
        XSearchRecentTweetsPipeline,
        XSearchRecentTweetsPipelineConfiguration,
        XSearchRecentTweetsPipelineParameters,
    )

    module = ABIModule.get_instance()
    # file_path mode never calls the API, but the pipeline config requires an
    # XIntegration; build it from the module's configured bearer token.
    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )
    pipeline = XSearchRecentTweetsPipeline(
        XSearchRecentTweetsPipelineConfiguration(
            x_integration=x_integration,
            triple_store=module.engine.services.triple_store,
            object_storage=module.engine.services.object_storage,
            graph_name=URIRef(graph_name or module.configuration.graph_name),
        )
    )
    logger.info(
        f"XOrchestration: mapping envelope {file_path!r} into the graph via "
        f"XSearchRecentTweetsPipeline"
    )
    pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            file_path=file_path,
            persist=True if persist is None else persist,
        )
    )


# ----- Recent-post COUNT helpers (shared by both orchestrations) -------------


def followed_count_entries(module) -> list[dict]:
    """Queries whose counts are followed / shown in the Recent Tweets app.

    The union of enabled ``count_recent_tweets_workflow`` entries and any
    ``search_recent_tweets_workflow`` filter that opts in via
    ``count_recent_tweets: true`` — deduped by query string. Both the count
    schedule and the search orchestration publish this same full list so the
    app catalog stays complete regardless of which one runs.
    """
    entries: list[dict] = []
    seen: set[str] = set()
    for entry in (
        getattr(module.configuration, "count_recent_tweets_workflow", []) or []
    ):
        if getattr(entry, "enabled", False) and entry.query not in seen:
            seen.add(entry.query)
            entries.append(
                {
                    "name": entry.name,
                    "query": entry.query,
                    "label": entry.label or entry.name,
                }
            )
    for flt in getattr(module.configuration, "search_recent_tweets_workflow", []) or []:
        if getattr(flt, "count_recent_tweets", False) and flt.query not in seen:
            seen.add(flt.query)
            entries.append({"name": flt.name, "query": flt.query, "label": flt.name})
    return entries


def run_count_for_query(module, query: str) -> dict:
    """Fetch the newest hourly counts for *query* and map them into the graph.

    Drives :class:`XCountRecentTweetsWorkflow` (7-day backfill on first run,
    last-full-hour afterwards) then maps every saved envelope via
    :class:`XCountRecentTweetsPipeline`. Idempotent per clock hour.
    """
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.x.pipelines.XCountRecentTweetsPipeline import (
        XCountRecentTweetsPipeline,
        XCountRecentTweetsPipelineConfiguration,
        XCountRecentTweetsPipelineParameters,
    )
    from naas_abi_marketplace.applications.x.workflows.XCountRecentTweetsWorkflow import (
        XCountRecentTweetsWorkflow,
        XCountRecentTweetsWorkflowConfiguration,
        XCountRecentTweetsWorkflowParameters,
    )

    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )
    workflow = XCountRecentTweetsWorkflow(
        XCountRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=module.engine.services.object_storage,
        )
    )
    pipeline = XCountRecentTweetsPipeline(
        XCountRecentTweetsPipelineConfiguration(
            x_integration=x_integration,
            triple_store=module.engine.services.triple_store,
            object_storage=module.engine.services.object_storage,
            graph_name=URIRef(_COUNT_GRAPH_NAME),
        )
    )
    output = workflow.run(XCountRecentTweetsWorkflowParameters(queries=[query]))
    mapped = 0
    for file_path in output.get("file_paths", []):
        try:
            pipeline.run(XCountRecentTweetsPipelineParameters(file_path=file_path))
            mapped += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"run_count_for_query[{query!r}]: failed to map {file_path!r} ({exc})"
            )
    return {"query": query, "buckets": output.get("total_buckets", 0), "mapped": mapped}


def publish_count_app(module) -> dict:
    """(Re)publish the Recent Tweets dashboard + snapshots for all followed queries."""
    from naas_abi_marketplace.applications.x.apps.x.hub import XCountAppHubBuilder

    hub = XCountAppHubBuilder(
        module.engine.services.object_storage,
        module.engine.services.triple_store,
        namespace=module.configuration.ontology_namespace,
    )
    return hub.publish(followed_count_entries(module))

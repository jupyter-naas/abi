"""Helpers shared across the X orchestrations.

Extracted from the former monolithic ``XOrchestration`` so each orchestration
file (search-workflow, event-driven, files-reprocess) can import the same
run-gating / pipeline-driving logic from a single site.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_marketplace.applications.x import ABIModule
from rdflib import URIRef

if TYPE_CHECKING:
    from naas_abi_marketplace.applications.x import XTweetSearchWorkflowConfiguration

# Sentinel so callers can force ``max_pages=None`` (unbounded sweep) explicitly,
# distinct from "not provided" (fall back to the filter's configured default).
_UNSET: Any = object()

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


def search_envelope_ingested(
    module,
    file_path: str,
    *,
    graph_name: str | None = None,
) -> bool:
    """True when a search envelope at *file_path* is already mapped into the graph.

    The search pipeline records each envelope's object-storage path on the
    ``SearchResultSet`` it builds (``x:file_path``). The ObjectPut sensor uses
    this to skip re-processing a file whose triples are already present — saving
    the file read + graph build — since re-mapping would only be an idempotent
    no-op. Fails **open** (returns ``False``) on any query error so a transient
    triple-store issue never drops ingestion; the pipeline's own dedupe is the
    backstop.
    """
    try:
        triple_store = module.engine.services.triple_store
    except Exception:  # noqa: BLE001 — no triple store → let ingestion proceed
        return False
    namespace = getattr(
        module.configuration, "ontology_namespace", "http://ontology.naas.ai/x/"
    )
    gname = graph_name or module.configuration.graph_name
    escaped = file_path.replace("\\", "\\\\").replace('"', '\\"')
    sparql = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX x:   <{namespace}>
    SELECT ?rs WHERE {{
      GRAPH <{gname}> {{
        ?rs rdf:type x:SearchResultSet ;
            x:file_path "{escaped}" .
      }}
    }} LIMIT 1
    """
    try:
        rows = SPARQLUtils(triple_store).results_to_list(triple_store.query(sparql))
    except Exception as exc:  # noqa: BLE001 — fail open (idempotent re-ingest is safe)
        logger.warning(
            f"search_envelope_ingested: probe failed for {file_path!r} ({exc}); "
            f"treating as not ingested"
        )
        return False
    return bool(rows)


# ----- Search fetch + inline-map helpers -------------------------------------


def run_search_workflow_for_filter(
    filter_config: XTweetSearchWorkflowConfiguration,
    op_cfg: dict | None = None,
    *,
    max_pages: Any = _UNSET,
) -> list[str]:
    """Fetch tweets for *filter_config* and persist the JSON envelopes.

    Returns the object-storage paths of the envelopes the workflow wrote. The
    graph mapping is **not** done here — each saved envelope's ObjectPut event
    drives XSearchRecentTweetsEventOrchestration to map it (or a caller maps them
    inline via :func:`run_search_and_map_for_query`). When ``count_recent_tweets``
    is set on the filter (or the launchpad), the recent-post count is followed and
    the Recent Tweets dashboard republished on the same tick.

    Pass ``max_pages`` explicitly (including ``None`` for an unbounded sweep) to
    override the filter/launchpad value — ``launchpad_override`` coerces a ``None``
    launchpad value back to the filter default, so a true "no page cap" must come
    through this argument.
    """
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
        XSearchRecentTweetsWorkflowConfiguration,
        XSearchRecentTweetsWorkflowParameters,
    )

    op_cfg = op_cfg or {}
    module = ABIModule.get_instance()
    query = launchpad_override(op_cfg, "query", filter_config.query)
    max_results = launchpad_override(op_cfg, "max_results", filter_config.max_results)
    if max_pages is _UNSET:
        max_pages = launchpad_override(op_cfg, "max_pages", filter_config.max_pages)
    sort_order = launchpad_override(op_cfg, "sort_order", filter_config.sort_order)
    save_every_pages = launchpad_override(
        op_cfg, "save_every_pages", filter_config.save_every_pages
    )
    save_every_tweets = launchpad_override(
        op_cfg, "save_every_tweets", filter_config.save_every_tweets
    )

    options: dict = {
        "max_results": max_results,
        "max_pages": max_pages,
        "sort_order": sort_order,
        "save_every_pages": save_every_pages,
        "save_every_tweets": save_every_tweets,
    }

    logger.info(
        f"run_search_workflow_for_filter[{filter_config.name}]: running "
        f"XSearchRecentTweetsWorkflow(query={query!r}, max_pages={max_pages}) — "
        f"fetch + save only (save_every_pages={save_every_pages}, "
        f"save_every_tweets={save_every_tweets})"
    )

    # XIntegration and the workflow both default datastore_path to the module's
    # configuration, so the envelopes the integration writes are the same ones
    # the workflow scans to recover since_id.
    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )
    workflow = XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=module.engine.services.object_storage,
            budget_key=filter_config.name,
            save_every_pages=save_every_pages,
            save_every_tweets=save_every_tweets,
            cost_per_tweet_usd=launchpad_override(
                op_cfg, "cost_per_tweet_usd", filter_config.cost_per_tweet_usd
            ),
            daily_max_tweets=launchpad_override(
                op_cfg, "daily_max_tweets", filter_config.daily_max_tweets
            ),
            daily_max_usd=launchpad_override(
                op_cfg, "daily_max_usd", filter_config.daily_max_usd
            ),
            monthly_max_tweets=launchpad_override(
                op_cfg, "monthly_max_tweets", filter_config.monthly_max_tweets
            ),
            monthly_max_usd=launchpad_override(
                op_cfg, "monthly_max_usd", filter_config.monthly_max_usd
            ),
        )
    )
    output = workflow.run(
        XSearchRecentTweetsWorkflowParameters(queries=[query], options=options)
    )

    file_paths: list[str] = []
    for item in output.get("results", []):
        paths = item.get("file_paths") or []
        if paths:
            file_paths.extend(paths)
        elif item.get("file_path"):
            file_paths.append(item["file_path"])
    logger.info(
        f"run_search_workflow_for_filter[{filter_config.name}]: saved "
        f"{len(file_paths)} envelope(s)."
    )

    # Optionally follow the recent-post COUNT for this query on the same tick.
    # App snapshot republish is gated by module ``app.publish``, not by this flag.
    count_recent_tweets = launchpad_override(
        op_cfg, "count_recent_tweets", filter_config.count_recent_tweets
    )
    if count_recent_tweets:
        try:
            count = run_count_for_query(module, query)
            logger.info(
                f"run_search_workflow_for_filter[{filter_config.name}]: followed "
                f"counts ({count['buckets']} bucket(s), {count['mapped']} "
                f"envelope(s) mapped)"
            )
        except Exception as exc:  # noqa: BLE001 — never fail the search on counts
            logger.warning(
                f"run_search_workflow_for_filter[{filter_config.name}]: count "
                f"follow-up failed ({exc}); search envelopes were still saved"
            )

    try:
        publish = publish_x_app(module)
        if publish.get("skipped"):
            logger.debug(
                f"run_search_workflow_for_filter[{filter_config.name}]: "
                f"app publish skipped ({publish.get('reason')})"
            )
        else:
            logger.info(
                f"run_search_workflow_for_filter[{filter_config.name}]: "
                f"republished X app ({publish.get('queries') or publish.get('queries_published')})"
            )
    except Exception as exc:  # noqa: BLE001 — never fail the search on publish
        logger.warning(
            f"run_search_workflow_for_filter[{filter_config.name}]: app "
            f"republish failed ({exc}); search envelopes were still saved"
        )

    return file_paths


def run_search_and_map_for_query(
    module,
    filter_config: XTweetSearchWorkflowConfiguration,
    *,
    max_pages: Any = _UNSET,
    follow_counts: bool = True,
    graph_name: str | None = None,
) -> dict:
    """Fetch (auto ``since_id``), save, and **map inline** tweets for *filter_config*.

    Closes the ingestion gap right before a downstream consumer (e.g. the daily
    report) reads the graph, instead of waiting for the asynchronous ObjectPut
    sensor. Every saved envelope is mapped synchronously via
    :class:`XSearchRecentTweetsPipeline` (idempotent — deterministic URIs make a
    re-map a no-op, and the ObjectPut sensor will skip these files via
    :func:`search_envelope_ingested`). Returns ``{query, file_paths, mapped}``.
    """
    op_cfg = {"count_recent_tweets": True} if follow_counts else {}
    file_paths = run_search_workflow_for_filter(
        filter_config, op_cfg, max_pages=max_pages
    )
    mapped = 0
    for file_path in file_paths:
        try:
            run_search_pipeline_for_file(file_path, graph_name=graph_name)
            mapped += 1
        except Exception as exc:  # noqa: BLE001 — map best-effort, keep going
            logger.warning(
                f"run_search_and_map_for_query[{filter_config.query!r}]: failed "
                f"to map {file_path!r} ({exc})"
            )
    return {
        "query": filter_config.query,
        "file_paths": file_paths,
        "mapped": mapped,
    }


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
            # Required: the fetch window is resolved from graph state (newest
            # mapped tweet + the hours already counted). Without it the
            # workflow has no ingestion front to follow and counts nothing.
            triple_store=module.engine.services.triple_store,
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

    # The in-progress hour goes through the pipeline's partial slot, which the
    # refresh overwrites. Routing it through the loop above would park a
    # non-final count in that hour's deduped IRI and freeze it there.
    partial_mapped = 0
    for entry in output.get("partial_file_paths", []):
        file_path = entry.get("file_path")
        if not file_path:
            continue
        try:
            pipeline.run(
                XCountRecentTweetsPipelineParameters(
                    file_path=file_path,
                    partial=True,
                    partial_end=entry.get("window_end"),
                )
            )
            partial_mapped += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"run_count_for_query[{query!r}]: failed to map partial "
                f"{file_path!r} ({exc})"
            )

    return {
        "query": query,
        "buckets": output.get("total_buckets", 0),
        "mapped": mapped,
        "partial_mapped": partial_mapped,
    }


def x_app_publish_enabled(module) -> bool:
    """Return whether module ``app.publish`` allows snapshot republish."""
    app_cfg = getattr(module.configuration, "app", None)
    if app_cfg is None:
        return True
    return bool(getattr(app_cfg, "publish", True))


def publish_x_app(module, *, enabled: bool | None = None) -> dict:
    """(Re)publish the X app dashboard + snapshots for all followed queries.

    When *enabled* is set (event/files ``app_publish``), that value wins.
    When *enabled* is ``None`` (count / search workflow), module
    ``app.publish`` applies (default true).
    """
    allow = bool(enabled) if enabled is not None else x_app_publish_enabled(module)
    if not allow:
        reason = "app_publish=false" if enabled is not None else "app.publish=false"
        logger.info(f"publish_x_app: skipped ({reason})")
        return {"skipped": True, "reason": reason}

    from naas_abi_marketplace.applications.x.apps.x.hub import XAppHubBuilder

    hub = XAppHubBuilder(
        module.engine.services.object_storage,
        module.engine.services.triple_store,
        namespace=module.configuration.ontology_namespace,
    )
    return hub.publish(followed_count_entries(module))


def republish_x_app_after_pipeline(
    module,
    *,
    source: str,
    app_publish: bool,
    ran: bool = True,
) -> dict:
    """Rebuild the X app dataset after a XSearchRecentTweetsPipeline run.

    Every orchestration that maps envelopes into the graph calls this, so the
    published dataset the app serves is refreshed on the same tick the graph
    changed — the app does no SPARQL of its own, so an un-run publish is the
    only way the dashboard can go stale.

    Never raises: a failed publish is logged and reported in the returned
    summary, but ingestion is what the run is for and must not be undone by a
    storage hiccup. *ran* false means the pipeline was not invoked at all (an
    empty sweep), in which case there is nothing new to publish.
    """
    if not ran:
        logger.info(f"{source}: pipeline did not run; no republish needed")
        return {"skipped": True, "reason": "pipeline did not run"}
    if not app_publish:
        logger.info(f"{source}: app_publish=false; skipped republish")
        return {"skipped": True, "reason": "app_publish=false"}
    try:
        publish = publish_x_app(module, enabled=True)
    except Exception as exc:  # noqa: BLE001 — never fail ingestion on publish
        logger.warning(
            f"{source}: app republish failed ({exc}); the graph was still "
            f"updated, so the next run will pick this up"
        )
        return {"failed": True, "error": str(exc)}
    if publish.get("skipped"):
        logger.info(f"{source}: app publish skipped ({publish.get('reason')})")
    else:
        logger.info(
            f"{source}: republished X app "
            f"({publish.get('queries') or publish.get('queries_published')})"
        )
    return publish

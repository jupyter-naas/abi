"""Bodies shared by the X orchestrations (Dagster) and the X flows (NATS).

Nothing here imports Dagster: the Dagster ops in ``orchestrations/`` and the
durable handlers in :mod:`naas_abi_marketplace.applications.x.flows` call the
same functions, so the two engines cannot drift. What stays in
``orchestrations/utils/_common.py`` is what only Dagster needs (run statuses,
sensor and schedule contexts, the report-window deferral).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from naas_abi_core import logger
from naas_abi_core.utils.SPARQL import SPARQLUtils
from rdflib import URIRef

if TYPE_CHECKING:
    from naas_abi_marketplace.applications.x import XTweetSearchWorkflowConfiguration

# Sentinel so callers can force ``max_pages=None`` (unbounded sweep) explicitly,
# distinct from "not provided" (fall back to the filter's configured default).
_UNSET: Any = object()

# Dedicated named graph for the recent-posts count triples (mirrors
# XCountRecentTweetsPipeline). Kept here so the count helpers below stay in one
# place shared by search/event orchestrations when count_recent_tweets is enabled.
_COUNT_GRAPH_NAME = "http://ontology.naas.ai/graph/x_recent_posts_count"


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


def jsonable(value: Any) -> Any:
    """*value* as plain JSON (what a durable step journals and a replay returns)."""
    return json.loads(json.dumps(value, default=str))


def run_search_pipeline_for_file(
    file_path: str,
    *,
    persist: bool | None = None,
    graph_name: str | None = None,
    module: Any = None,
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

    if module is None:
        from naas_abi_marketplace.applications.x import ABIModule

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
    effective_persist = True if persist is None else persist
    pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            file_path=file_path,
            persist=effective_persist,
        )
    )
    if effective_persist:
        try:
            from intelligence.utils.OsintPipelinePendingWork import (  # type: ignore[import-not-found]
                enqueue_pending_location_extractions_from_envelope,
            )

            enqueue_pending_location_extractions_from_envelope(
                module.engine.services.triple_store,
                module.engine.services.object_storage,
                file_path,
                ontology_namespace=getattr(
                    module.configuration,
                    "ontology_namespace",
                    "http://ontology.naas.ai/x/",
                ),
                graph_name=str(graph_name or module.configuration.graph_name),
            )
        except Exception as exc:  # noqa: BLE001 — ingestion must not fail on queue write
            logger.warning(
                f"XOrchestration: pending location enqueue failed for {file_path!r} ({exc})"
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


def envelope_paths_in_dataset(module, file_paths: list[str]) -> set[str]:
    """Subset of *file_paths* already recorded in ``x.envelopes_v1``.

    Fails open (empty set) when Dataset Service is unavailable or the probe
    errors, matching :func:`search_envelope_in_dataset` per-path behaviour.
    """
    try:
        if not module.engine.services.dataset_available():
            return set()
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
            envelope_paths_in_dataset as lookup_envelope_paths,
        )

        return lookup_envelope_paths(
            module.engine.services.dataset,
            file_paths,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "envelope_paths_in_dataset: bulk probe failed (%s); "
            "treating all paths as not ingested",
            exc,
        )
        return set()


def search_envelope_in_dataset(module, file_path: str) -> bool:
    """True when *file_path* is recorded in ``x.envelopes_v1``.

    Fails open (``False``) when Dataset Service is unavailable or the probe
    errors, so ingestion still runs rather than dropping projection.
    """
    try:
        if not module.engine.services.dataset_available():
            return False
        from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
            envelope_already_ingested,
        )

        return envelope_already_ingested(
            module.engine.services.dataset, normalize_envelope_path(file_path)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"search_envelope_in_dataset: probe failed for {file_path!r} ({exc}); "
            f"treating as not ingested"
        )
        return False


def normalize_envelope_path(path: str) -> str:
    return str(path or "").strip().lstrip("/")


def search_envelope_fully_projected(
    module,
    file_path: str,
    *,
    graph_name: str | None = None,
) -> bool:
    """True when the envelope is mapped in the graph and listed in ``envelopes_v1``."""
    return search_envelope_ingested(
        module, file_path, graph_name=graph_name
    ) and search_envelope_in_dataset(module, file_path)


# ----- Search fetch + inline-map helpers -------------------------------------


def build_search_workflow(
    module,
    filter_config: XTweetSearchWorkflowConfiguration,
    op_cfg: dict | None = None,
):
    """The :class:`XSearchRecentTweetsWorkflow` for *filter_config* (spend caps
    included), with *op_cfg* overrides applied the way the Dagster launchpad does."""
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
        XSearchRecentTweetsWorkflowConfiguration,
    )

    op_cfg = op_cfg or {}
    # XIntegration and the workflow both default datastore_path to the module's
    # configuration, so the envelopes the integration writes are the same ones
    # the workflow scans to recover since_id.
    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )
    return XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=module.engine.services.object_storage,
            budget_key=filter_config.name,
            save_every_pages=launchpad_override(
                op_cfg, "save_every_pages", filter_config.save_every_pages
            ),
            save_every_tweets=launchpad_override(
                op_cfg, "save_every_tweets", filter_config.save_every_tweets
            ),
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


def search_budget_blocked(
    module, filter_config: XTweetSearchWorkflowConfiguration
) -> str | None:
    """Why *filter_config*'s daily or monthly spend cap forbids a fetch now, else ``None``.

    The same all-or-nothing check :class:`XSearchRecentTweetsWorkflow` makes
    before it calls the X API, so a caller can stop before fetching.
    """
    return build_search_workflow(module, filter_config).budget_exhausted_reason()


def fetch_search_envelopes(
    module,
    filter_config: XTweetSearchWorkflowConfiguration,
    op_cfg: dict | None = None,
    *,
    max_pages: Any = _UNSET,
) -> dict:
    """Fetch tweets for *filter_config* and persist the JSON envelopes.

    Returns ``{"file_paths": [...], "total_new_tweets": n, "budget_blocked":
    bool, "budget_reason": str | None}``: the object-storage paths of the
    envelopes the workflow wrote, and whether the spend guard stopped the fetch.
    Nothing is mapped, counted or published here.

    Pass ``max_pages`` explicitly (including ``None`` for an unbounded sweep) to
    override the filter/launchpad value — ``launchpad_override`` coerces a ``None``
    launchpad value back to the filter default, so a true "no page cap" must come
    through this argument.
    """
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflowParameters,
    )

    op_cfg = op_cfg or {}
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
        f"fetch_search_envelopes[{filter_config.name}]: running "
        f"XSearchRecentTweetsWorkflow(query={query!r}, max_pages={max_pages}) — "
        f"fetch + save only (save_every_pages={save_every_pages}, "
        f"save_every_tweets={save_every_tweets})"
    )

    workflow = build_search_workflow(module, filter_config, op_cfg)
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
        f"fetch_search_envelopes[{filter_config.name}]: saved "
        f"{len(file_paths)} envelope(s)."
    )
    return {
        "file_paths": file_paths,
        "total_new_tweets": int(output.get("total_new_tweets") or 0),
        "budget_blocked": bool(output.get("budget_blocked")),
        "budget_reason": output.get("budget_reason"),
    }


def follow_counts_after_search(
    module,
    filter_config: XTweetSearchWorkflowConfiguration,
    op_cfg: dict | None = None,
) -> dict | None:
    """Follow the recent-post COUNT for the filter's query on the same tick.

    ``None`` when the filter (or the launchpad) does not opt in. Never raises:
    the envelopes are saved, and a failed count must not undo that.
    """
    op_cfg = op_cfg or {}
    query = launchpad_override(op_cfg, "query", filter_config.query)
    if not launchpad_override(
        op_cfg, "count_recent_tweets", filter_config.count_recent_tweets
    ):
        return None
    try:
        count = run_count_for_query(module, query)
    except Exception as exc:  # noqa: BLE001 — never fail the search on counts
        logger.warning(
            f"follow_counts_after_search[{filter_config.name}]: count "
            f"follow-up failed ({exc}); search envelopes were still saved"
        )
        return None
    logger.info(
        f"follow_counts_after_search[{filter_config.name}]: followed "
        f"counts ({count['buckets']} bucket(s), {count['mapped']} "
        f"envelope(s) mapped)"
    )
    return count


def publish_app_after_search(
    module,
    filter_config: XTweetSearchWorkflowConfiguration,
    op_cfg: dict | None = None,
) -> dict | None:
    """Republish the app when the filter opts in (``app_publish``), else ``None``.

    Republishing reads the whole graph and re-renders every snapshot, so it
    dominates the tick and grows with the graph — opt-in per filter, and off by
    default. The hourly x_build_pipeline_hub schedule publishes from the same
    state, so leaving this off costs at most an hour of dashboard staleness.
    Never raises, as :func:`follow_counts_after_search`.
    """
    op_cfg = op_cfg or {}
    if not launchpad_override(op_cfg, "app_publish", filter_config.app_publish):
        logger.debug(
            f"publish_app_after_search[{filter_config.name}]: app publish "
            f"skipped (app_publish=false); x_build_pipeline_hub republishes on its schedule"
        )
        return None
    try:
        publish = publish_x_app(module, enabled=True)
    except Exception as exc:  # noqa: BLE001 — never fail the search on publish
        logger.warning(
            f"publish_app_after_search[{filter_config.name}]: app "
            f"republish failed ({exc}); search envelopes were still saved"
        )
        return None
    if publish.get("skipped"):
        logger.debug(
            f"publish_app_after_search[{filter_config.name}]: "
            f"app publish skipped ({publish.get('reason')})"
        )
    else:
        logger.info(
            f"publish_app_after_search[{filter_config.name}]: "
            f"republished X app ({publish.get('queries') or publish.get('queries_published')})"
        )
    return publish


def run_search_workflow_for_filter(
    filter_config: XTweetSearchWorkflowConfiguration,
    op_cfg: dict | None = None,
    *,
    max_pages: Any = _UNSET,
) -> list[str]:
    """Fetch tweets for *filter_config*, persist the JSON envelopes, and run the
    same-tick follow-ups (counts, app publish) the Dagster search op always ran.

    Returns the object-storage paths of the envelopes the workflow wrote. The
    graph mapping is **not** done here — each saved envelope's ObjectPut event
    drives XSearchRecentTweetsEventOrchestration to map it (or a caller maps them
    inline via :func:`run_search_and_map_for_query`). The durable flow
    (``flows/search.py``) calls the same pieces as separate checkpointed steps.
    """
    from naas_abi_marketplace.applications.x import ABIModule

    module = ABIModule.get_instance()
    fetched = fetch_search_envelopes(module, filter_config, op_cfg, max_pages=max_pages)
    follow_counts_after_search(module, filter_config, op_cfg)
    publish_app_after_search(module, filter_config, op_cfg)
    return fetched["file_paths"]


def sync_x_dataset_paths_batched(
    module,
    envelope_paths: list[str],
    *,
    batch_size: int = 64,
    context=None,
) -> dict:
    """Sync many envelope paths in bounded batches (Files fallback sweeps)."""
    if not envelope_paths:
        return {"skipped": True, "reason": "no_paths", "batches": 0}
    summaries: list[dict] = []
    for offset in range(0, len(envelope_paths), batch_size):
        batch = envelope_paths[offset : offset + batch_size]
        summaries.append(sync_x_dataset_paths(module, batch, context=context))
    return {"batches": len(summaries), "summaries": summaries}


def sync_x_dataset_paths(
    module,
    envelope_paths: list[str],
    *,
    context=None,
) -> dict:
    """Incremental dataset projection for exact envelope paths.

    *context* is a Dagster evaluation context: when given, the sync defers while
    a daily report job runs. The durable flows pass none.
    """
    if context is not None:
        from naas_abi_marketplace.applications.x.orchestrations.utils._common import (
            report_jobs_in_progress,
        )

        if report_jobs_in_progress(context):
            logger.info(
                "sync_x_dataset_paths: deferred while report pipeline in progress"
            )
            return {"skipped": True, "reason": "report_window"}
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.sync import (
        sync_envelope_paths,
    )

    return sync_envelope_paths(module, envelope_paths)


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


# ----- Recent-post COUNT helpers ---------------------------------------------


def followed_count_entries(module) -> list[dict]:
    """Queries whose counts are followed / shown in the Recent Tweets app.

    The union of enabled ``count_recent_tweets_workflow`` entries and any
    ``search_recent_tweets_workflow`` filter that opts in via
    ``count_recent_tweets: true`` — deduped by query string. Search and event
    orchestrations publish this same full list so the app catalog stays complete.
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


def _count_integration(module):
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )

    return XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )


def fetch_counts_for_query(module, query: str) -> dict:
    """Fetch the newest hourly counts for *query* and persist their envelopes.

    Drives :class:`XCountRecentTweetsWorkflow` (7-day backfill on first run,
    last-full-hour afterwards). Returns its output: ``total_buckets``,
    ``file_paths`` (complete hours), ``partial_file_paths`` (the hour in progress,
    ``{"file_path", "window_end"}`` each) and per-query ``results``. The graph is
    not touched.
    """
    from naas_abi_marketplace.applications.x.workflows.XCountRecentTweetsWorkflow import (
        XCountRecentTweetsWorkflow,
        XCountRecentTweetsWorkflowConfiguration,
        XCountRecentTweetsWorkflowParameters,
    )

    workflow = XCountRecentTweetsWorkflow(
        XCountRecentTweetsWorkflowConfiguration(
            x_integration=_count_integration(module),
            object_storage=module.engine.services.object_storage,
            # Required: the fetch window is resolved from graph state (newest
            # mapped tweet + the hours already counted). Without it the
            # workflow has no ingestion front to follow and counts nothing.
            triple_store=module.engine.services.triple_store,
        )
    )
    return workflow.run(XCountRecentTweetsWorkflowParameters(queries=[query]))


def map_counts_for_query(module, query: str, output: dict) -> dict:
    """Map the count envelopes of *output* (see :func:`fetch_counts_for_query`)
    into the count graph with :class:`XCountRecentTweetsPipeline`.

    Idempotent per clock hour. Returns ``{"mapped": n, "partial_mapped": n}``.
    """
    from naas_abi_marketplace.applications.x.pipelines.XCountRecentTweetsPipeline import (
        XCountRecentTweetsPipeline,
        XCountRecentTweetsPipelineConfiguration,
        XCountRecentTweetsPipelineParameters,
    )

    pipeline = XCountRecentTweetsPipeline(
        XCountRecentTweetsPipelineConfiguration(
            x_integration=_count_integration(module),
            triple_store=module.engine.services.triple_store,
            object_storage=module.engine.services.object_storage,
            graph_name=URIRef(_COUNT_GRAPH_NAME),
        )
    )
    mapped = 0
    for file_path in output.get("file_paths", []):
        try:
            pipeline.run(XCountRecentTweetsPipelineParameters(file_path=file_path))
            mapped += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"map_counts_for_query[{query!r}]: failed to map {file_path!r} ({exc})"
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
                f"map_counts_for_query[{query!r}]: failed to map partial "
                f"{file_path!r} ({exc})"
            )
    return {"mapped": mapped, "partial_mapped": partial_mapped}


def sync_counts_dataset(module, query: str, output: dict) -> dict | None:
    """Project the count envelopes of *output* into Dataset Service.

    ``None`` when there is nothing to sync or dataset sync is off. A failed sync
    is logged and returns ``None``: the count graph was already updated.
    """
    paths_to_sync = [
        str(path).strip()
        for path in output.get("file_paths", [])
        if str(path or "").strip()
    ] + [
        str(entry.get("file_path") or "").strip()
        for entry in output.get("partial_file_paths", [])
        if str(entry.get("file_path") or "").strip()
    ]
    if not paths_to_sync:
        return None
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
        x_dataset_sync_enabled,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.sync import (
        sync_envelope_paths,
    )

    if not x_dataset_sync_enabled(module):
        return None
    try:
        return sync_envelope_paths(module, paths_to_sync)
    except Exception as exc:  # noqa: BLE001 — graph counts still mapped
        logger.warning(
            f"sync_counts_dataset[{query!r}]: dataset sync failed "
            f"({exc}); count graph was still updated"
        )
        return None


def run_count_for_query(module, query: str) -> dict:
    """Fetch the newest hourly counts for *query* and map them into the graph.

    :func:`fetch_counts_for_query`, then :func:`map_counts_for_query`, then
    :func:`sync_counts_dataset`. Idempotent per clock hour.
    """
    output = fetch_counts_for_query(module, query)
    mapped = map_counts_for_query(module, query, output)
    return {
        "query": query,
        "buckets": output.get("total_buckets", 0),
        **mapped,
        "dataset_sync": sync_counts_dataset(module, query, output),
    }


def x_app_publish_enabled(module) -> bool:
    """Return whether module ``app.publish`` allows snapshot republish."""
    app_cfg = getattr(module.configuration, "app", None)
    if app_cfg is None:
        return True
    return bool(getattr(app_cfg, "publish", True))


def publish_x_app(
    module,
    *,
    enabled: bool | None = None,
) -> dict:
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

    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
        x_dataset_read_enabled,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.hub import XAppHubBuilder

    if not x_dataset_read_enabled(module):
        logger.info(
            "publish_x_app: skipped (app.dataset.read_enabled is false — "
            "Fuseki/Parquet snapshot publish was removed)"
        )
        return {"skipped": True, "reason": "dataset_read_disabled"}

    dataset = getattr(module.engine.services, "dataset", None)
    if dataset is None:
        logger.warning(
            "publish_x_app: app.dataset.read_enabled but Dataset Service "
            "is not wired — skipping publish"
        )
        return {"skipped": True, "reason": "dataset_service_missing"}

    hub = XAppHubBuilder(
        module.engine.services.object_storage,
        module.engine.services.triple_store,
        namespace=module.configuration.ontology_namespace,
    )
    return hub.publish(followed_count_entries(module), dataset=dataset)


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

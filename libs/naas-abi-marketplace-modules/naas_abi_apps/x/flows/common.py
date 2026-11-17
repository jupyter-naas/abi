"""The synchronous bodies of the X flows: graph, envelopes, counts, app.

Each function takes ``module``, the module's ``SyncModule`` (``module.sync``:
``configuration``, blocking ``engine.services``, ``run(coro)``), and runs in a
worker thread: a workflow passes it to ``ctx.step``, which runs a sync function
off the loop, and a job to ``asyncio.to_thread``. On the loop, the blocking
services raise.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from naas_abi_apps.x.services import logger, results_to_list
from rdflib import URIRef

if TYPE_CHECKING:
    from naas_abi_apps.x.configuration import XTweetSearchWorkflowConfiguration

# Dedicated named graph for the recent-posts count triples (mirrors
# XCountRecentTweetsPipeline).
_COUNT_GRAPH_NAME = "http://ontology.naas.ai/graph/x_recent_posts_count"


def jsonable(value: Any) -> Any:
    """*value* as plain JSON (what a durable step journals and a replay returns)."""
    return json.loads(json.dumps(value, default=str))


def run_search_pipeline_for_file(
    module: Any,
    file_path: str,
    *,
    persist: bool | None = None,
    graph_name: str | None = None,
) -> None:
    """Map a persisted search_recent_tweets envelope into the graph.

    Runs :class:`XSearchRecentTweetsPipeline` in its ``file_path`` mode: it
    reads ``{query, options, results, started_at, ended_at}`` from *file_path*
    (relative to the object-storage root) instead of calling the X API, so it
    needs no integration. Idempotent: the pipeline's label-based dedupe makes a
    re-run on the same file a no-op.
    """
    from naas_abi_apps.x.pipelines.XSearchRecentTweetsPipeline import (
        XSearchRecentTweetsPipeline,
        XSearchRecentTweetsPipelineConfiguration,
        XSearchRecentTweetsPipelineParameters,
    )

    configuration = module.configuration
    services = module.engine.services
    pipeline = XSearchRecentTweetsPipeline(
        XSearchRecentTweetsPipelineConfiguration(
            triple_store=services.triple_store,
            object_storage=services.object_storage,
            graph_name=URIRef(graph_name or configuration.graph_name),
            namespace=configuration.ontology_namespace,
            datastore_path=configuration.datastore_path,
        )
    )
    logger.info(
        f"X mapping: envelope {file_path!r} into the graph via XSearchRecentTweetsPipeline"
    )
    pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            file_path=file_path,
            persist=True if persist is None else persist,
        )
    )


def search_envelope_ingested(
    module: Any,
    file_path: str,
    *,
    graph_name: str | None = None,
) -> bool:
    """True when a search envelope at *file_path* is already mapped into the graph.

    The search pipeline records each envelope's object-storage path on the
    ``SearchResultSet`` it builds (``x:file_path``). Fails **open** (``False``)
    on any query error so a transient triple-store issue never drops
    ingestion; the pipeline's own dedupe is the backstop.
    """
    configuration = module.configuration
    gname = graph_name or configuration.graph_name
    escaped = file_path.replace("\\", "\\\\").replace('"', '\\"')
    sparql = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX x:   <{configuration.ontology_namespace}>
    SELECT ?rs WHERE {{
      GRAPH <{gname}> {{
        ?rs rdf:type x:SearchResultSet ;
            x:file_path "{escaped}" .
      }}
    }} LIMIT 1
    """
    try:
        rows = results_to_list(module.engine.services.triple_store.query(sparql))
    except Exception as exc:  # noqa: BLE001 - fail open (idempotent re-ingest is safe)
        logger.warning(
            f"search_envelope_ingested: probe failed for {file_path!r} ({exc}); "
            f"treating as not ingested"
        )
        return False
    return bool(rows)


def _dataset_probe_enabled(module: Any) -> bool:
    """Whether the dataset can hold envelopes: with its sync off, none is there."""
    from naas_abi_apps.x.x_proxy.dataset.store import x_dataset_sync_enabled

    return x_dataset_sync_enabled(module)


def envelope_paths_in_dataset(module: Any, file_paths: list[str]) -> set[str]:
    """Subset of *file_paths* already recorded in ``envelopes_v1`` (normalized).

    Fails open (empty set) when the dataset sync is off or the probe errors,
    matching :func:`search_envelope_in_dataset` per-path behaviour.
    """
    try:
        if not _dataset_probe_enabled(module):
            return set()
        from naas_abi_apps.x.x_proxy.dataset.store import (
            envelope_paths_in_dataset as lookup_envelope_paths,
        )

        return lookup_envelope_paths(module.engine.services.dataset, file_paths)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"envelope_paths_in_dataset: bulk probe failed ({exc}); "
            "treating all paths as not ingested"
        )
        return set()


def search_envelope_in_dataset(module: Any, file_path: str) -> bool:
    """True when *file_path* is recorded in ``envelopes_v1``.

    Fails open (``False``) when the dataset sync is off or the probe errors,
    so ingestion still runs rather than dropping projection.
    """
    try:
        if not _dataset_probe_enabled(module):
            return False
        from naas_abi_apps.x.x_proxy.dataset.store import envelope_already_ingested

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
    module: Any,
    file_path: str,
    *,
    graph_name: str | None = None,
) -> bool:
    """True when the envelope is mapped in the graph and listed in ``envelopes_v1``."""
    return search_envelope_ingested(
        module, file_path, graph_name=graph_name
    ) and search_envelope_in_dataset(module, file_path)


# ----- Search fetch ------------------------------------------------------------------


def build_search_workflow(
    module: Any, filter_config: XTweetSearchWorkflowConfiguration
) -> Any:
    """The :class:`XSearchRecentTweetsWorkflow` for *filter_config*, spend caps
    included (its ledger is keyed by the filter's name)."""
    from naas_abi_apps.x.integrations.XIntegration import x_integration_for
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
        XSearchRecentTweetsWorkflowConfiguration,
    )

    configuration = module.configuration
    return XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=x_integration_for(module),
            object_storage=module.engine.services.object_storage,
            run=module.run,
            triple_store=None,
            datastore_path=configuration.datastore_path,
            graph_name=configuration.graph_name,
            budget_key=filter_config.name,
            cost_per_tweet_usd=filter_config.cost_per_tweet_usd,
            daily_max_tweets=filter_config.daily_max_tweets,
            daily_max_usd=filter_config.daily_max_usd,
            monthly_max_tweets=filter_config.monthly_max_tweets,
            monthly_max_usd=filter_config.monthly_max_usd,
            save_every_pages=filter_config.save_every_pages,
            save_every_tweets=filter_config.save_every_tweets,
        )
    )


def search_budget_blocked(
    module: Any, filter_config: XTweetSearchWorkflowConfiguration
) -> str | None:
    """Why *filter_config*'s daily or monthly spend cap forbids a fetch now, else ``None``.

    The same all-or-nothing check :class:`XSearchRecentTweetsWorkflow` makes
    before it calls the X API, so a caller can stop before fetching.
    """
    return build_search_workflow(module, filter_config).budget_exhausted_reason()


def fetch_search_envelopes(
    module: Any,
    filter_config: XTweetSearchWorkflowConfiguration,
    *,
    saved_paths: list[str] | None = None,
) -> dict:
    """Fetch tweets for *filter_config* and persist the JSON envelopes.

    Returns ``{"file_paths": [...], "total_new_tweets": n, "budget_blocked":
    bool, "budget_reason": str | None}``: the object-storage paths of the
    envelopes the workflow wrote, and whether the spend guard stopped the fetch.
    Nothing is mapped, counted or published here.

    A fetch that fails part-way has saved the batches before the failing one.
    Pass ``saved_paths`` to learn them: the envelopes saved so far are added to it
    before the error propagates.
    """
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflowParameters,
    )

    options: dict = {
        "max_results": filter_config.max_results,
        "max_pages": filter_config.max_pages,
        "sort_order": filter_config.sort_order,
        "save_every_pages": filter_config.save_every_pages,
        "save_every_tweets": filter_config.save_every_tweets,
    }
    logger.info(
        f"fetch_search_envelopes[{filter_config.name}]: running "
        f"XSearchRecentTweetsWorkflow(query={filter_config.query!r}, "
        f"max_pages={filter_config.max_pages}): fetch and save only "
        f"(save_every_pages={filter_config.save_every_pages}, "
        f"save_every_tweets={filter_config.save_every_tweets})"
    )
    workflow = build_search_workflow(module, filter_config)
    try:
        output = workflow.run(
            XSearchRecentTweetsWorkflowParameters(
                queries=[filter_config.query], options=options
            )
        )
    except Exception:
        if saved_paths is not None:
            saved_paths.extend(workflow.saved_file_paths())
        raise

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


# ----- Dataset ---------------------------------------------------------------------


def sync_x_dataset_paths_batched(
    module: Any,
    envelope_paths: list[str],
    *,
    batch_size: int = 64,
) -> dict:
    """Sync many envelope paths into the dataset, in bounded batches."""
    if not envelope_paths:
        return {"skipped": True, "reason": "no_paths", "batches": 0}
    summaries: list[dict] = []
    for offset in range(0, len(envelope_paths), batch_size):
        batch = envelope_paths[offset : offset + batch_size]
        summaries.append(sync_x_dataset_paths(module, batch))
    return {"batches": len(summaries), "summaries": summaries}


def sync_x_dataset_paths(module: Any, envelope_paths: list[str]) -> dict:
    """Incremental dataset projection for exact envelope paths."""
    from naas_abi_apps.x.x_proxy.dataset.sync import sync_envelope_paths

    return sync_envelope_paths(module, envelope_paths)


# ----- Recent-post COUNT helpers ---------------------------------------------


def followed_count_entries(module: Any) -> list[dict]:
    """Queries whose counts are followed / shown in the Recent Tweets app.

    The union of enabled ``count_recent_tweets_workflow`` entries and any
    ``search_recent_tweets_workflow`` filter that opts in via
    ``count_recent_tweets: true``, deduped by query string.
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


def fetch_counts_for_query(module: Any, query: str) -> dict:
    """Fetch the newest hourly counts for *query* and persist their envelopes.

    Drives :class:`XCountRecentTweetsWorkflow` (7-day backfill on first run,
    last-full-hour afterwards). Returns its output: ``total_buckets``,
    ``file_paths`` (complete hours), ``partial_file_paths`` (the hour in progress,
    ``{"file_path", "window_end"}`` each) and per-query ``results``. The graph is
    not touched.
    """
    from naas_abi_apps.x.integrations.XIntegration import x_integration_for
    from naas_abi_apps.x.workflows.XCountRecentTweetsWorkflow import (
        XCountRecentTweetsWorkflow,
        XCountRecentTweetsWorkflowConfiguration,
        XCountRecentTweetsWorkflowParameters,
    )

    configuration = module.configuration
    services = module.engine.services
    workflow = XCountRecentTweetsWorkflow(
        XCountRecentTweetsWorkflowConfiguration(
            x_integration=x_integration_for(module),
            object_storage=services.object_storage,
            run=module.run,
            # Required: the fetch window is resolved from graph state (newest
            # mapped tweet + the hours already counted). Without it the
            # workflow has no ingestion front to follow and counts nothing.
            triple_store=services.triple_store,
            datastore_path=configuration.datastore_path,
            # Where the search mapping writes the tweets (the ingestion front).
            tweet_graph_name=configuration.graph_name,
            namespace=configuration.ontology_namespace,
        )
    )
    return workflow.run(XCountRecentTweetsWorkflowParameters(queries=[query]))


def map_counts_for_query(module: Any, query: str, output: dict) -> dict:
    """Map the count envelopes of *output* (see :func:`fetch_counts_for_query`)
    into the count graph with :class:`XCountRecentTweetsPipeline`.

    Idempotent per clock hour. Returns ``{"mapped": n, "partial_mapped": n}``.
    """
    from naas_abi_apps.x.pipelines.XCountRecentTweetsPipeline import (
        XCountRecentTweetsPipeline,
        XCountRecentTweetsPipelineConfiguration,
        XCountRecentTweetsPipelineParameters,
    )

    configuration = module.configuration
    services = module.engine.services
    pipeline = XCountRecentTweetsPipeline(
        XCountRecentTweetsPipelineConfiguration(
            triple_store=services.triple_store,
            object_storage=services.object_storage,
            graph_name=URIRef(_COUNT_GRAPH_NAME),
            namespace=configuration.ontology_namespace,
            datastore_path=configuration.datastore_path,
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


def sync_counts_dataset(module: Any, query: str, output: dict) -> dict | None:
    """Project the count envelopes of *output* into the dataset.

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
    from naas_abi_apps.x.x_proxy.dataset.store import x_dataset_sync_enabled
    from naas_abi_apps.x.x_proxy.dataset.sync import sync_envelope_paths

    if not x_dataset_sync_enabled(module):
        return None
    try:
        return sync_envelope_paths(module, paths_to_sync)
    except Exception as exc:  # noqa: BLE001 - graph counts still mapped
        logger.warning(
            f"sync_counts_dataset[{query!r}]: dataset sync failed "
            f"({exc}); count graph was still updated"
        )
        return None


# ----- App -------------------------------------------------------------------------


def x_app_publish_enabled(module: Any) -> bool:
    """Return whether module ``app.publish`` allows snapshot republish."""
    app_cfg = getattr(module.configuration, "app", None)
    if app_cfg is None:
        return True
    return bool(getattr(app_cfg, "publish", True))


def publish_x_app(module: Any, *, enabled: bool | None = None) -> dict:
    """(Re)publish the X app dashboard + snapshots for all followed queries.

    When *enabled* is set (a filter's or a sweep's ``app_publish``), that value
    wins. When it is ``None`` (the ``build_app`` job), module ``app.publish``
    applies (default true).
    """
    allow = bool(enabled) if enabled is not None else x_app_publish_enabled(module)
    if not allow:
        reason = "app_publish=false" if enabled is not None else "app.publish=false"
        logger.info(f"publish_x_app: skipped ({reason})")
        return {"skipped": True, "reason": reason}

    from naas_abi_apps.x.x_proxy.dataset.store import x_dataset_read_enabled
    from naas_abi_apps.x.x_proxy.hub import XAppHubBuilder

    if not x_dataset_read_enabled(module):
        logger.info(
            "publish_x_app: skipped (app.dataset.read_enabled is false: the app "
            "snapshots are read from the dataset)"
        )
        return {"skipped": True, "reason": "dataset_read_disabled"}

    services = module.engine.services
    hub = XAppHubBuilder(
        services.object_storage,
        services.triple_store,
        namespace=module.configuration.ontology_namespace,
    )
    return hub.publish(followed_count_entries(module), dataset=services.dataset)

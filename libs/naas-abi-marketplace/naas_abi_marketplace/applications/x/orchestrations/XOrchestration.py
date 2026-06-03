import re
from typing import Optional

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from rdflib import URIRef

from naas_abi_marketplace.applications.x import (
    ABIModule,
    XTweetIngestionConfiguration,
)

IN_PROGRESS_RUN_STATUSES = [
    dg.DagsterRunStatus.QUEUED,
    dg.DagsterRunStatus.NOT_STARTED,
    dg.DagsterRunStatus.STARTING,
    dg.DagsterRunStatus.STARTED,
]


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", value) or "filter"


def _has_in_progress_run(context: dg.SensorEvaluationContext, job_name: str) -> bool:
    runs = context.instance.get_runs(
        filters=dg.RunsFilter(
            job_name=job_name,
            statuses=IN_PROGRESS_RUN_STATUSES,
        ),
        limit=1,
    )
    return len(runs) > 0


def _get_last_seen_tweet_id(graph_name: str, query_string: str) -> Optional[str]:
    """Return the largest ``tweet_id`` already ingested for *query_string*.

    The X v2 ``since_id`` parameter takes the snowflake id of the most-recent
    known tweet; comparing as strings would order ``"99"`` after ``"100"`` so
    we cast to xsd:integer in SPARQL and pick the MAX. Returns ``None`` when
    no tweet has been ingested for this query yet (first run).
    """
    module = ABIModule.get_instance()
    triple_store = module.engine.services.triple_store
    escaped = query_string.replace("\\", "\\\\").replace('"', '\\"')
    sparql = f"""
        PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
        PREFIX x:    <http://ontology.naas.ai/x/>

        SELECT (MAX(xsd:integer(?tweetId)) AS ?maxId)
        WHERE {{
          GRAPH <{graph_name}> {{
            ?query rdf:type x:SearchQuery ;
                   x:query_string "{escaped}" .
            ?process rdf:type x:SearchRecentTweets ;
                     x:usesSearchQuery ?query ;
                     x:producesSearchResult ?resultSet .
            ?tweet rdf:type x:Tweet ;
                   x:tweet_id ?tweetId ;
                   x:isContainedInSearchResultSet ?resultSet .
          }}
        }}
    """
    try:
        rows = list(triple_store.query(sparql))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XOrchestration: failed to compute since_id for query "
            f"{query_string!r} ({exc}); ingesting without since_id"
        )
        return None
    if not rows:
        return None
    # SPARQL SELECT returns ResultRow objects; access the single projected
    # binding by name. ResultRow is dict-like at runtime but rdflib types
    # it as a union, so the explicit cast keeps mypy happy.
    from typing import cast as _cast

    from rdflib.query import ResultRow

    max_id = _cast(ResultRow, rows[0]).get("maxId")
    if max_id is None:
        return None
    return str(max_id)


def _build_tweet_ingestion_job_sensor(
    config: XTweetIngestionConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    """Build the (job, sensor) pair that ingests tweets matching *config*.

    Why a job-per-filter rather than one parametrised job: Dagster sensors
    are bound to a single job and the sensor cursor / in-progress check both
    key on the job name. Keeping one job per filter means each filter has
    its own independently-throttled queue — slow filters can't block fast
    ones.
    """

    safe = _safe_name(config.name)
    job_name = f"x_tweet_ingestion_{safe}"
    op_name = f"x_tweet_ingestion_op_{safe}"
    sensor_name = f"x_tweet_ingestion_sensor_{safe}"

    @dg.op(name=op_name)
    def tweet_ingestion_op():
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
        graph_name = module.configuration.graph_name

        since_id = _get_last_seen_tweet_id(graph_name, config.query)
        # Request the rich fields the rest of the pipeline maps into the
        # graph (XUser via author_id, TweetPublicMetrics via public_metrics,
        # TweetLanguage via lang, tweet_created_at). Without these the X v2
        # search endpoint only returns {id, text} and the agent's
        # engagement / language / author queries all come up empty.
        options: dict = {
            "max_results": config.max_results,
            "max_pages": config.max_pages,
            "sort_order": "recency",
            "tweet_fields": [
                "author_id",
                "created_at",
                "public_metrics",
                "lang",
                "edit_history_tweet_ids",
            ],
        }
        if since_id is not None:
            options["since_id"] = since_id

        logger.info(
            f"XOrchestration[{config.name}]: running search_recent_tweets("
            f"query={config.query!r}, since_id={since_id})"
        )

        x_integration = XIntegration(
            XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
        )
        pipeline = XSearchRecentTweetsPipeline(
            XSearchRecentTweetsPipelineConfiguration(
                x_integration=x_integration,
                triple_store=module.engine.services.triple_store,
                graph_name=URIRef(graph_name),
            )
        )
        pipeline.run(
            XSearchRecentTweetsPipelineParameters(
                query=config.query,
                options=options,
                persist=True,
            )
        )

    graph = dg.GraphDefinition(name=job_name, node_defs=[tweet_ingestion_op])
    # Run the op in the dagster code-server's own process. Dagster's default
    # multiprocess executor forks a fresh Python subprocess per step that
    # has to re-import naas_abi_core and re-bootstrap the engine (every
    # ontology insertion, the nexus SQLAlchemy setup, …) — ~10 s of pure
    # overhead for a one-HTTP-call op, and the second bootstrap contends
    # with the already-running api on oxigraph + nexus.db, which surfaces
    # as "Step finished without success or failure event" / interrupted
    # children. Sharing the code-server's already-warm engine is both
    # faster and removes the cross-process race.
    job = graph.to_job(name=job_name, executor_def=dg.in_process_executor)

    @dg.sensor(
        name=sensor_name,
        description=(
            f"Poll X v2 search_recent_tweets for filter '{config.name}' "
            f"(query={config.query!r}) every {config.interval_seconds}s "
            f"and ingest any tweets newer than the last seen tweet id."
        ),
        job=job,
        minimum_interval_seconds=config.interval_seconds,
    )
    def tweet_ingestion_sensor(context: dg.SensorEvaluationContext):
        if _has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")
        # Use a stable run_key so re-evaluation within the same tick does
        # not enqueue duplicates — Dagster deduplicates RunRequests sharing
        # a run_key with currently-active runs.
        return [dg.RunRequest(run_key=None)]

    return job, tweet_ingestion_sensor


class XOrchestration(DagsterOrchestration):
    """Dagster orchestration for the X application.

    Spawns one (job, sensor) pair per entry in
    ``ABIModule.configuration.tweet_ingestion_pipelines``. The sensor wakes
    every ``interval_seconds`` and, unless a run for that filter is already
    in flight, triggers the ingestion job for that filter — which in turn
    calls X v2 ``search_recent_tweets`` with ``since_id`` set to the largest
    tweet id already in the graph for that query, so each tick only fetches
    the delta.
    """

    @classmethod
    def New(cls) -> "XOrchestration":
        module = ABIModule.get_instance()

        jobs: list[dg.JobDefinition] = []
        sensors: list[dg.SensorDefinition] = []

        seen_names: set[str] = set()
        for ingestion_config in module.configuration.tweet_ingestion_pipelines:
            if ingestion_config.name in seen_names:
                logger.warning(
                    f"XOrchestration: duplicate tweet_ingestion_pipelines "
                    f"name {ingestion_config.name!r}; skipping the duplicate"
                )
                continue
            seen_names.add(ingestion_config.name)
            job, sensor = _build_tweet_ingestion_job_sensor(ingestion_config)
            jobs.append(job)
            sensors.append(sensor)

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=jobs,
                sensors=sensors,
            )
        )

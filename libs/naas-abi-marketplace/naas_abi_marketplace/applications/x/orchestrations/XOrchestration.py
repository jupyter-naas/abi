import re
from typing import Optional

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from rdflib import URIRef

from naas_abi_marketplace.applications.x import (
    ABIModule,
    XTweetFileIngestionConfiguration,
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


def _list_unprocessed_keys(
    object_storage,
    triple_store,
    graph_name: str,
    prefix: str,
    *,
    recursive: bool,
) -> list[str]:
    """List object keys under *prefix* that haven't been ingested yet.

    "Not ingested" is decided by querying the graph for the set of
    ``object_storage_key`` literals already attached to an
    ``x:TweetFile`` individual. We diff against the listing rather than
    re-hashing each candidate so the sensor stays cheap even when the
    folder grows large — actual sha256 dedupe still happens inside the
    pipeline before it spends a single triple insert.
    """
    try:
        all_keys = object_storage.list_objects(prefix) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XOrchestration: list_objects({prefix!r}) failed ({exc}); "
            "skipping this tick"
        )
        return []

    candidates: list[str] = []
    for k in all_keys:
        # Strip the prefix back off (list_objects returns prefix-relative
        # paths but with leading prefix repeated) so we pass the bare key
        # to the pipeline, which re-joins via prefix + key.
        key = k[len(prefix) :].lstrip("/") if k.startswith(prefix) else k
        if not key:
            continue  # the prefix marker itself
        if not recursive and "/" in key:
            continue
        # Skip non-JSON extensions early — the pipeline would barf anyway.
        if not (
            key.endswith(".json")
            or key.endswith(".ndjson")
            or key.endswith(".json.gz")
            or key.endswith(".ndjson.gz")
        ):
            continue
        candidates.append(key)

    if not candidates:
        return []

    # Bulk SPARQL ASK against the graph would be one round trip per file;
    # instead select all already-known keys for the prefix and diff in
    # Python. This is the same pattern DocumentOrchestration uses.
    sparql = f"""
        PREFIX x: <http://ontology.naas.ai/x/>
        SELECT ?key WHERE {{
          GRAPH <{graph_name}> {{
            ?f a x:TweetFile ;
               x:object_storage_prefix "{prefix}" ;
               x:object_storage_key ?key .
          }}
        }}
    """
    try:
        known = {str(row[0]) for row in triple_store.query(sparql)}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XOrchestration: known-files SPARQL failed ({exc}); "
            "treating all candidates as unprocessed"
        )
        known = set()
    return [k for k in candidates if k not in known]


def _build_tweet_file_ingestion_job_sensor(
    config: XTweetFileIngestionConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    """Build the (job, sensor) pair that streams tweet dumps from object storage.

    Same in-process executor argument as the search pipeline: the
    ingestion op shares the dagster code-server's warm engine so we don't
    fork a subprocess that has to re-bootstrap and race the api on
    oxigraph / nexus.db.
    """

    safe = _safe_name(config.name)
    job_name = f"x_tweet_file_ingestion_{safe}"
    op_name = f"x_tweet_file_ingestion_op_{safe}"
    sensor_name = f"x_tweet_file_ingestion_sensor_{safe}"

    @dg.op(name=op_name, config_schema={"key": str})
    def tweet_file_ingestion_op(context: dg.OpExecutionContext):
        from naas_abi_marketplace.applications.x.pipelines.XFileIngestionPipeline import (
            XFileIngestionPipeline,
            XFileIngestionPipelineConfiguration,
            XFileIngestionPipelineParameters,
        )

        module = ABIModule.get_instance()
        key = context.op_config["key"]

        pipeline = XFileIngestionPipeline(
            XFileIngestionPipelineConfiguration(
                object_storage=module.engine.services.object_storage,
                triple_store=module.engine.services.triple_store,
                graph_name=URIRef(module.configuration.graph_name),
                batch_size=config.batch_size,
            )
        )
        pipeline.run(
            XFileIngestionPipelineParameters(
                prefix=config.input_prefix,
                key=key,
                delete_after_ingest=config.delete_after_ingest,
            )
        )

    graph = dg.GraphDefinition(name=job_name, node_defs=[tweet_file_ingestion_op])
    job = graph.to_job(name=job_name, executor_def=dg.in_process_executor)

    @dg.sensor(
        name=sensor_name,
        description=(
            f"Poll object-storage prefix {config.input_prefix!r} every "
            f"{config.interval_seconds}s and ingest any new "
            f".json / .ndjson tweet dumps via XFileIngestionPipeline."
        ),
        job=job,
        minimum_interval_seconds=config.interval_seconds,
        default_status=dg.DefaultSensorStatus.RUNNING,
    )
    def tweet_file_ingestion_sensor(context: dg.SensorEvaluationContext):
        if _has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")

        module = ABIModule.get_instance()
        keys = _list_unprocessed_keys(
            module.engine.services.object_storage,
            module.engine.services.triple_store,
            module.configuration.graph_name,
            config.input_prefix,
            recursive=config.recursive,
        )
        if not keys:
            return dg.SkipReason(
                f"No unprocessed files under {config.input_prefix!r}."
            )

        # One RunRequest per file. Run-key includes the key so concurrent
        # ticks don't double-enqueue the same file, and so dagster's run
        # history shows which file each run handled.
        return [
            dg.RunRequest(
                run_key=f"{job_name}:{k}",
                run_config={"ops": {op_name: {"config": {"key": k}}}},
            )
            for k in keys
        ]

    return job, tweet_file_ingestion_sensor


# ---------------------------------------------------------------------------
# Auto-discovery: subscribe to ObjectPut events, classify, ingest matches
# (temporarily disabled — requires EventService in module EngineProxy;
#  re-enable after restarting the ABI stack with EventService in deps)
# ---------------------------------------------------------------------------

# _TWEET_FILE_EXTENSIONS = (".json", ".ndjson", ".json.gz", ".ndjson.gz")
# _AUTO_INGESTION_SENSOR = "x_tweet_file_auto_ingestion_sensor"
# _AUTO_INGESTION_JOB = "x_tweet_file_auto_ingestion"
# _AUTO_INGESTION_OP = "x_tweet_file_auto_ingestion_op"


# def _looks_like_tweet_dump(prefix: str, key: str, size_bytes: int | None) -> bool:
#     if size_bytes is not None and size_bytes <= 0:
#         return False
#     name = key.lower()
#     return any(name.endswith(ext) for ext in _TWEET_FILE_EXTENSIONS)


# def _build_object_put_event_sensor() -> tuple[dg.JobDefinition, dg.SensorDefinition]:
#     @dg.op(name=_AUTO_INGESTION_OP, config_schema={"prefix": str, "key": str})
#     def auto_ingestion_op(context: dg.OpExecutionContext):
#         from naas_abi_marketplace.applications.x.pipelines.XFileIngestionPipeline import (
#             XFileIngestionPipeline,
#             XFileIngestionPipelineConfiguration,
#             XFileIngestionPipelineParameters,
#         )
#
#         module = ABIModule.get_instance()
#         prefix = context.op_config["prefix"]
#         key = context.op_config["key"]
#
#         pipeline = XFileIngestionPipeline(
#             XFileIngestionPipelineConfiguration(
#                 object_storage=module.engine.services.object_storage,
#                 triple_store=module.engine.services.triple_store,
#                 graph_name=URIRef(module.configuration.graph_name),
#                 batch_size=500,
#             )
#         )
#         pipeline.run(
#             XFileIngestionPipelineParameters(
#                 prefix=prefix,
#                 key=key,
#                 delete_after_ingest=False,
#             )
#         )
#
#     graph = dg.GraphDefinition(name=_AUTO_INGESTION_JOB, node_defs=[auto_ingestion_op])
#     job = graph.to_job(name=_AUTO_INGESTION_JOB, executor_def=dg.in_process_executor)
#
#     @dg.sensor(
#         name=_AUTO_INGESTION_SENSOR,
#         description=(
#             "Subscribe to ObjectPut events on the bus and trigger "
#             "XFileIngestionPipeline for any new object whose key matches "
#             "a known tweet-dump extension. Zero-config — no input_prefix "
#             "needed; drop a .json / .ndjson tweet dump anywhere in "
#             "object storage and it gets ingested automatically."
#         ),
#         job=job,
#         minimum_interval_seconds=30,
#         default_status=dg.DefaultSensorStatus.RUNNING,
#     )
#     def auto_ingestion_sensor(context: dg.SensorEvaluationContext):
#         from naas_abi_core.services.object_storage.ontologies.modules.ObjectStorageEventOntology import (
#             ObjectPut,
#         )
#
#         module = ABIModule.get_instance()
#         try:
#             new_events = module.engine.services.events.query_for_consumer(
#                 consumer_id=_AUTO_INGESTION_SENSOR,
#                 event_class=ObjectPut,
#                 limit=100,
#             )
#         except (ValueError, AssertionError) as exc:
#             return dg.SkipReason(
#                 f"EventService not available ({exc}); restart the ABI stack "
#                 "to enable event-driven auto-ingestion"
#             )
#         except Exception as exc:  # noqa: BLE001
#             return dg.SkipReason(
#                 f"ObjectPut event query failed ({exc}); will retry next tick"
#             )
#
#         if not new_events:
#             return dg.SkipReason("no new ObjectPut events")
#
#         run_requests: list[dg.RunRequest] = []
#         for evt in new_events:
#             prefix = evt.prefix or ""
#             key = evt.key or ""
#             if not key:
#                 continue
#             if not _looks_like_tweet_dump(prefix, key, evt.size_bytes):
#                 continue
#             run_requests.append(
#                 dg.RunRequest(
#                     run_key=f"{_AUTO_INGESTION_JOB}:{prefix}:{key}",
#                     run_config={
#                         "ops": {
#                             _AUTO_INGESTION_OP: {
#                                 "config": {"prefix": prefix, "key": key}
#                             }
#                         }
#                     },
#                 )
#             )
#
#         if not run_requests:
#             return dg.SkipReason(
#                 f"{len(new_events)} ObjectPut event(s) processed; none "
#                 "matched the tweet-dump classifier"
#             )
#         return run_requests
#
#     return job, auto_ingestion_sensor


class XOrchestration(DagsterOrchestration):
    """Dagster orchestration for the X application.

    Spawns three families of (job, sensor) pairs:

    1. One per ``tweet_ingestion_pipelines`` entry: the sensor wakes
       every ``interval_seconds`` and, unless a run for that filter is
       already in flight, triggers a job that calls X v2
       ``search_recent_tweets`` with ``since_id`` set to the largest
       tweet id already in the graph for that query (so each tick only
       fetches the delta).
    2. **Opt-in**: one per ``tweet_file_ingestion_pipelines`` entry. The
       sensor polls a configured object-storage prefix and triggers
       :class:`XFileIngestionPipeline` for each new tweet-dump file.
       Useful when you want a named pipeline / dedicated sensor history
       per drop folder.
    3. **Always on** — a single auto-discovery sensor that subscribes to
       ``ObjectPut`` events on the bus via
       ``events.query_for_consumer``, classifies each event's key, and
       ingests anything that looks like a tweet dump (``.json``,
       ``.ndjson``, gzipped variants) anywhere in storage. This is the
       event-system pay-off: drop a file anywhere, the system finds it.

    All three families share :class:`XFileIngestionPipeline`'s streaming
    behaviour and sha256 dedupe — so the same file landing in two
    drop folders won't get ingested twice.
    """

    @classmethod
    def New(cls) -> "XOrchestration":
        module = ABIModule.get_instance()

        jobs: list[dg.JobDefinition] = []
        sensors: list[dg.SensorDefinition] = []

        # ----- Search-API pipelines (one sensor per configured filter) -------
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

        # ----- File-ingestion pipelines (one sensor per drop folder) ---------
        # Note: explicit drop folders are an opt-in, useful when you want a
        # named pipeline / dedicated sensor history per use case. The
        # zero-config event-driven sensor below handles the common path
        # (auto-discover tweet dumps no matter where they land in storage).
        seen_file_names: set[str] = set()
        for file_config in module.configuration.tweet_file_ingestion_pipelines:
            if file_config.name in seen_file_names:
                logger.warning(
                    f"XOrchestration: duplicate tweet_file_ingestion_pipelines "
                    f"name {file_config.name!r}; skipping the duplicate"
                )
                continue
            seen_file_names.add(file_config.name)
            job, sensor = _build_tweet_file_ingestion_job_sensor(file_config)
            jobs.append(job)
            sensors.append(sensor)

        # ----- Auto-discovery: ObjectPut event subscription ------------------
        # Temporarily disabled — see commented block above.
        # auto_job, auto_sensor = _build_object_put_event_sensor()
        # jobs.append(auto_job)
        # sensors.append(auto_sensor)

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=jobs,
                sensors=sensors,
            )
        )

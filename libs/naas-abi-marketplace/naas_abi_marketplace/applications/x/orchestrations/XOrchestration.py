import posixpath
import re

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import (
    ABIModule,
    XTweetFileIngestionConfiguration,
    XTweetSearchWorkflowConfiguration,
)
from rdflib import URIRef

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


def _run_search_pipeline_for_file(file_path: str) -> None:
    """Map a persisted search_recent_tweets envelope into the graph.

    Runs :class:`XSearchRecentTweetsPipeline` in its ``file_path`` mode: it
    reads ``{query, options, results, started_at, ended_at}`` from *file_path*
    (relative to the object-storage root) instead of calling the X API, so the
    full SearchQuery / SearchResultSet / SearchRecentTweets structure is built
    from the same envelope that XFileIngestionPipeline / XSearchRecentTweets-
    Workflow just wrote. Idempotent — the pipeline's label-based dedupe makes a
    re-run on the same file a no-op.
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
            graph_name=URIRef(module.configuration.graph_name),
        )
    )
    logger.info(
        f"XOrchestration: mapping envelope {file_path!r} into the graph via "
        f"XSearchRecentTweetsPipeline"
    )
    pipeline.run(
        XSearchRecentTweetsPipelineParameters(file_path=file_path, persist=True)
    )


def _build_search_workflow_job_sensor(
    config: XTweetSearchWorkflowConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    """Build the (job, sensor) pair that ingests tweets matching *config* via
    :class:`XSearchRecentTweetsWorkflow`.

    Same job-per-filter rationale as :func:`_build_tweet_ingestion_job_sensor`
    (Dagster sensors bind to a single job; per-filter jobs throttle
    independently). The job is two chained ops: the first drives the *workflow*
    (``since_id`` recovered from the persisted JSON envelopes in object storage)
    and returns each persisted envelope's ``file_path``; the second feeds those
    paths to :class:`XSearchRecentTweetsPipeline` in ``file_path`` mode, which
    maps the full SearchQuery / SearchResultSet / SearchRecentTweets structure
    into the graph from the same files.
    """

    safe = _safe_name(config.name)
    job_name = f"x_search_workflow_{safe}"
    op_name = f"x_search_workflow_op_{safe}"
    pipeline_op_name = f"x_search_workflow_pipeline_op_{safe}"
    sensor_name = f"x_search_workflow_sensor_{safe}"

    @dg.op(name=op_name)
    def search_workflow_op() -> list[str]:
        from naas_abi_marketplace.applications.x.integrations.XIntegration import (
            XIntegration,
            XIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
            XSearchRecentTweetsWorkflow,
            XSearchRecentTweetsWorkflowConfiguration,
            XSearchRecentTweetsWorkflowParameters,
        )

        module = ABIModule.get_instance()

        # Request the rich fields the rest of the pipeline maps into the graph
        # (XUser via author_id, TweetPublicMetrics via public_metrics,
        # TweetLanguage via lang, tweet_created_at). Without these the X v2
        # search endpoint only returns {id, text} and the agent's engagement /
        # language / author queries all come up empty.
        options: dict = {
            "max_results": config.max_results,
            "max_pages": config.max_pages,
            "sort_order": config.sort_order,
            # "tweet_fields": [
            #     "author_id",
            #     "created_at",
            #     "public_metrics",
            #     "lang",
            #     "edit_history_tweet_ids",
            # ],
        }

        logger.info(
            f"XOrchestration[{config.name}]: running XSearchRecentTweetsWorkflow("
            f"query={config.query!r}, persist={config.persist})"
        )

        # XIntegration and the workflow both default datastore_path to the
        # module's configuration, so the envelopes the integration writes are
        # the same ones the workflow scans to recover since_id.
        x_integration = XIntegration(
            XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
        )
        workflow = XSearchRecentTweetsWorkflow(
            XSearchRecentTweetsWorkflowConfiguration(
                x_integration=x_integration,
                object_storage=module.engine.services.object_storage,
                # Per-filter spend guard: ledger keyed by this filter's name so
                # each filter caps its own daily / monthly X API spend.
                budget_key=config.name,
                cost_per_tweet_usd=config.cost_per_tweet_usd,
                daily_max_tweets=config.daily_max_tweets,
                daily_max_usd=config.daily_max_usd,
                monthly_max_tweets=config.monthly_max_tweets,
                monthly_max_usd=config.monthly_max_usd,
            )
        )
        output = workflow.run(
            XSearchRecentTweetsWorkflowParameters(
                queries=[config.query],
                options=options,
                persist=config.persist,
            )
        )

        # Hand each persisted envelope's path to the downstream pipeline op so
        # the full SearchQuery / SearchRecentTweets structure is mapped from the
        # same file the workflow just wrote.
        return [
            item["file_path"]
            for item in output.get("results", [])
            if item.get("file_path")
        ]

    @dg.op(name=pipeline_op_name)
    def search_workflow_pipeline_op(file_paths: list[str]) -> None:
        for file_path in file_paths:
            _run_search_pipeline_for_file(file_path)

    # In-process executor for the same reason as the other X jobs: share the
    # code-server's warm engine instead of forking a subprocess that has to
    # re-bootstrap and race the api on oxigraph / nexus.db.
    @dg.graph(name=job_name)
    def search_workflow_graph():
        # File-path output of the workflow op triggers the pipeline op.
        search_workflow_pipeline_op(search_workflow_op())

    job = search_workflow_graph.to_job(
        name=job_name, executor_def=dg.in_process_executor
    )

    @dg.sensor(
        name=sensor_name,
        description=(
            f"Poll X v2 search_recent_tweets for filter '{config.name}' "
            f"(query={config.query!r}) every {config.interval_seconds}s via "
            f"XSearchRecentTweetsWorkflow and ingest any tweets newer than the "
            f"last persisted newest_id."
        ),
        job=job,
        minimum_interval_seconds=config.interval_seconds,
    )
    def search_workflow_sensor(context: dg.SensorEvaluationContext):
        if _has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")
        return [dg.RunRequest(run_key=None)]

    return job, search_workflow_sensor


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
            return dg.SkipReason(f"No unprocessed files under {config.input_prefix!r}.")

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
# Event-driven ingestion: subscribe to ObjectPut events under the
# search_recent_tweets datastore prefix and stream each new envelope into the
# X graph via XFileIngestionPipeline.
# ---------------------------------------------------------------------------

# The XSearchRecentTweetsWorkflow / XIntegration write their query envelopes to
# ``<datastore_path>/search_recent_tweets/<slug>/<ts>_<slug>.json`` and the
# ObjectStorageService strips the leading ``storage/`` before publishing the
# ObjectPut event, so the event's ``prefix`` always starts with this value.
_SEARCH_RECENT_TWEETS_PREFIX = "x/search_recent_tweets"
_TWEET_FILE_EXTENSIONS = (".json", ".ndjson", ".json.gz", ".ndjson.gz")
_SEARCH_INGESTION_SENSOR = "x_search_recent_tweets_put_sensor"
_SEARCH_INGESTION_JOB = "x_search_recent_tweets_ingestion"
_SEARCH_INGESTION_OP = "x_search_recent_tweets_ingestion_op"
_SEARCH_PIPELINE_OP = "x_search_recent_tweets_pipeline_op"


def _is_search_recent_tweets_put(prefix: str, key: str, size_bytes: int | None) -> bool:
    """True when an ObjectPut targets a tweet envelope under the watched prefix."""
    if size_bytes is not None and size_bytes <= 0:
        return False
    if not key:
        return False
    normalized = prefix.strip("/")
    if not (
        normalized == _SEARCH_RECENT_TWEETS_PREFIX
        or normalized.startswith(_SEARCH_RECENT_TWEETS_PREFIX + "/")
    ):
        return False
    return key.lower().endswith(_TWEET_FILE_EXTENSIONS)


def _build_search_recent_tweets_event_sensor() -> tuple[
    dg.JobDefinition, dg.SensorDefinition
]:
    """Build the (job, sensor) pair that ingests search_recent_tweets envelopes.

    The sensor drains undelivered ``ObjectPut`` events via
    ``events.query_for_consumer`` (durable cursor — every put is seen exactly
    once), keeps only those landing under ``x/search_recent_tweets``, and emits
    one RunRequest per file. The job is two chained ops: the first streams that
    envelope through :class:`XFileIngestionPipeline` (sha256 dedupe makes a
    redelivered or re-put file a no-op) and returns its ``prefix/key`` path; the
    second feeds that path to :class:`XSearchRecentTweetsPipeline` in
    ``file_path`` mode to map the full search structure from the same file. Same
    in-process executor argument as the other X jobs: share the dagster
    code-server's warm engine instead of forking a subprocess that re-bootstraps
    and races the api on oxigraph / nexus.db.
    """

    @dg.op(name=_SEARCH_INGESTION_OP, config_schema={"prefix": str, "key": str})
    def search_ingestion_op(context: dg.OpExecutionContext) -> str:
        from naas_abi_marketplace.applications.x.pipelines.XFileIngestionPipeline import (
            XFileIngestionPipeline,
            XFileIngestionPipelineConfiguration,
            XFileIngestionPipelineParameters,
        )

        module = ABIModule.get_instance()
        prefix = context.op_config["prefix"]
        key = context.op_config["key"]

        logger.info(
            f"XOrchestration: ingesting search_recent_tweets envelope "
            f"{prefix}/{key} via XFileIngestionPipeline"
        )
        pipeline = XFileIngestionPipeline(
            XFileIngestionPipelineConfiguration(
                object_storage=module.engine.services.object_storage,
                triple_store=module.engine.services.triple_store,
                graph_name=URIRef(module.configuration.graph_name),
                batch_size=500,
            )
        )
        pipeline.run(
            XFileIngestionPipelineParameters(
                prefix=prefix,
                key=key,
                delete_after_ingest=False,
            )
        )

        # Emit the envelope path so the downstream op maps the full search
        # structure from the same file via XSearchRecentTweetsPipeline.
        return posixpath.join(prefix, key)

    @dg.op(name=_SEARCH_PIPELINE_OP)
    def search_pipeline_op(file_path: str) -> None:
        _run_search_pipeline_for_file(file_path)

    @dg.graph(name=_SEARCH_INGESTION_JOB)
    def search_ingestion_graph():
        # File-path output of the ingestion op triggers the pipeline op.
        search_pipeline_op(search_ingestion_op())

    job = search_ingestion_graph.to_job(
        name=_SEARCH_INGESTION_JOB, executor_def=dg.in_process_executor
    )

    @dg.sensor(
        name=_SEARCH_INGESTION_SENSOR,
        description=(
            "Subscribe to ObjectPut events on the bus and trigger "
            "XFileIngestionPipeline for every new object written under "
            f"{_SEARCH_RECENT_TWEETS_PREFIX!r} (the search_recent_tweets "
            "envelopes). Event-driven — no polling of object storage; each "
            "put is processed exactly once via the durable consumer cursor."
        ),
        job=job,
        minimum_interval_seconds=30,
        default_status=dg.DefaultSensorStatus.RUNNING,
    )
    def search_ingestion_sensor(context: dg.SensorEvaluationContext):
        from naas_abi_core.services.object_storage.ontologies.modules.ObjectStorageEventOntology import (
            ObjectPut,
        )

        module = ABIModule.get_instance()
        if not module.engine.services.events_available():
            return dg.SkipReason(
                "EventService not available; restart the ABI stack with the "
                "event service enabled to drive event-based ingestion"
            )
        try:
            new_events = module.engine.services.events.query_for_consumer(
                consumer_id=_SEARCH_INGESTION_SENSOR,
                event_class=ObjectPut,
                limit=100,
            )
        except Exception as exc:  # noqa: BLE001
            return dg.SkipReason(
                f"ObjectPut event query failed ({exc}); will retry next tick"
            )

        if not new_events:
            return dg.SkipReason("no new ObjectPut events")

        run_requests: list[dg.RunRequest] = []
        for evt in new_events:
            prefix = evt.prefix or ""
            key = evt.key or ""
            if not _is_search_recent_tweets_put(prefix, key, evt.size_bytes):
                continue
            run_requests.append(
                dg.RunRequest(
                    # Run-key includes prefix+key so the same envelope can't be
                    # double-enqueued and dagster's history shows which file
                    # each run handled.
                    run_key=f"{_SEARCH_INGESTION_JOB}:{prefix}:{key}",
                    run_config={
                        "ops": {
                            _SEARCH_INGESTION_OP: {
                                "config": {"prefix": prefix, "key": key}
                            }
                        }
                    },
                )
            )

        if not run_requests:
            return dg.SkipReason(
                f"{len(new_events)} ObjectPut event(s) processed; none landed "
                f"under {_SEARCH_RECENT_TWEETS_PREFIX!r}"
            )
        return run_requests

    return job, search_ingestion_sensor


class XOrchestration(DagsterOrchestration):
    """Dagster orchestration for the X application.

    Spawns three families of (job, sensor) pairs:

    1. One per ``search_recent_tweets_workflow`` entry: the sensor wakes
       every ``interval_seconds`` and, unless a run for that filter is
       already in flight, triggers a job that drives
       :class:`XSearchRecentTweetsWorkflow` — ``since_id`` is recovered from
       the persisted JSON envelopes in object storage — then feeds each
       persisted envelope's ``file_path`` to
       :class:`XSearchRecentTweetsPipeline` to map it into the graph.
    2. **Opt-in**: one per ``file_ingestion_pipeline`` entry. The
       sensor polls a configured object-storage prefix and triggers
       :class:`XFileIngestionPipeline` for each new tweet-dump file.
       Useful when you want a named pipeline / dedicated sensor history
       per drop folder.
    3. **Always on** — a single event-driven sensor that subscribes to
       ``ObjectPut`` events on the bus via ``events.query_for_consumer``
       and, for every new object written under ``x/search_recent_tweets``
       (the envelopes the search workflow / integration persist), runs
       :class:`XFileIngestionPipeline` then feeds the same file's path to
       :class:`XSearchRecentTweetsPipeline`. This is the event-system
       pay-off: a tweet search lands an envelope, the put event drives
       ingestion with no polling.

    All three families share :class:`XFileIngestionPipeline`'s streaming
    behaviour and sha256 dedupe — so the same file landing in two
    drop folders won't get ingested twice.
    """

    @classmethod
    def New(cls) -> "XOrchestration":
        module = ABIModule.get_instance()

        jobs: list[dg.JobDefinition] = []
        sensors: list[dg.SensorDefinition] = []

        # ----- Search-workflow pipelines (one sensor per configured filter) ---
        # Each job drives XSearchRecentTweetsWorkflow (datastore-derived
        # since_id, .ttl written next to each envelope).
        seen_workflow_names: set[str] = set()
        for workflow_config in module.configuration.search_recent_tweets_workflow:
            if workflow_config.name in seen_workflow_names:
                logger.warning(
                    f"XOrchestration: duplicate search_recent_tweets_workflow "
                    f"name {workflow_config.name!r}; skipping the duplicate"
                )
                continue
            seen_workflow_names.add(workflow_config.name)
            job, sensor = _build_search_workflow_job_sensor(workflow_config)
            jobs.append(job)
            sensors.append(sensor)

        # ----- File-ingestion pipelines (one sensor per drop folder) ---------
        # Note: explicit drop folders are an opt-in, useful when you want a
        # named pipeline / dedicated sensor history per use case. The
        # zero-config event-driven sensor below handles the common path
        # (auto-discover tweet dumps no matter where they land in storage).
        seen_file_names: set[str] = set()
        for file_config in module.configuration.file_ingestion_pipeline:
            if file_config.name in seen_file_names:
                logger.warning(
                    f"XOrchestration: duplicate file_ingestion_pipeline "
                    f"name {file_config.name!r}; skipping the duplicate"
                )
                continue
            seen_file_names.add(file_config.name)
            job, sensor = _build_tweet_file_ingestion_job_sensor(file_config)
            jobs.append(job)
            sensors.append(sensor)

        # ----- Event-driven: ingest search_recent_tweets envelopes -----------
        # A single always-on sensor subscribes to ObjectPut events and streams
        # every new envelope written under x/search_recent_tweets into the
        # graph via XFileIngestionPipeline.
        event_job, event_sensor = _build_search_recent_tweets_event_sensor()
        jobs.append(event_job)
        sensors.append(event_sensor)

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=jobs,
                sensors=sensors,
            )
        )

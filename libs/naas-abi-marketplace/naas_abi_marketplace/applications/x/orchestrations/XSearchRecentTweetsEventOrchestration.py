"""Event-driven ingestion orchestration for the X application.

A single (job, sensor) pair that subscribes to ``ObjectPut`` events on the bus
and, for every new object written under ``x/search_recent_tweets`` (the
envelopes the search workflow / integration persist), runs
:class:`XFileIngestionPipeline` then feeds the same file's path to
:class:`XSearchRecentTweetsPipeline`. This is the event-system pay-off: a tweet
search lands an envelope, the put event drives ingestion with no polling.

The sensor is **disabled by default** (``DefaultSensorStatus.STOPPED``); enable
it explicitly from the Dagster UI.

⚠️ Double-execution note: this sensor watches the very prefix the
:class:`XSearchWorkflowOrchestration` writes to. If both are enabled, each
envelope is mapped into the graph twice (once directly by the workflow job, once
here via the put event). It stays correct — XFileIngestionPipeline's sha256
dedupe and the pipeline's label-based dedupe make the second pass a no-op — but
it is redundant work. Enable only one of the two ingestion paths.
"""

import posixpath

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.orchestrations.utils import (
    run_search_pipeline_for_file,
)
from rdflib import URIRef

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
            f"XSearchRecentTweetsEventOrchestration: ingesting search_recent_tweets "
            f"envelope {prefix}/{key} via XFileIngestionPipeline"
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
        run_search_pipeline_for_file(file_path)

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
        default_status=dg.DefaultSensorStatus.STOPPED,
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


class XSearchRecentTweetsEventOrchestration(DagsterOrchestration):
    """A single event-driven (job, sensor) pair that subscribes to ``ObjectPut``
    events and ingests every new envelope written under ``x/search_recent_tweets``
    via :class:`XFileIngestionPipeline` then :class:`XSearchRecentTweetsPipeline`.
    Sensor disabled by default.
    """

    @classmethod
    def New(cls) -> "XSearchRecentTweetsEventOrchestration":
        job, sensor = _build_search_recent_tweets_event_sensor()
        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=[job],
                sensors=[sensor],
            )
        )

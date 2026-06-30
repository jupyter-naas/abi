"""Event-driven ingestion orchestration for the X application.

One (job, sensor) pair per ``search_recent_tweets_event`` config entry. Each
sensor subscribes to ``ObjectPut`` events on the bus and, for every new envelope
written under that entry's ``prefix`` (the JSON files
:class:`XSearchWorkflowOrchestration` saves), feeds the file's path straight to
:class:`XSearchRecentTweetsPipeline` in ``file_path`` mode to map the full
SearchQuery / SearchResultSet / SearchRecentTweets structure into the graph.
This is the event-system pay-off: the search workflow only fetches and saves;
the put event then drives all graph mapping here, with no polling.

Each entry's sensor, watched prefix and ingestion knobs (persist, events drained
per tick, evaluation interval) come from the ``search_recent_tweets_event`` list
in the module config. The config defaults to an empty list (no sensors); add
entries to create them. Sensors are **disabled by default**
(``DefaultSensorStatus.STOPPED``); set ``enabled: true`` on an entry to create
its sensor RUNNING, or enable it from the Dagster UI.

Launch manually from the Dagster launchpad to replay a single envelope: set
``prefix`` and ``key`` on the entry's pipeline op (required). Optional fields
fall back to that entry's config defaults.

Launchpad example (filter ``search_envelopes``)::

    ops:
      x_search_recent_tweets_pipeline_op_search_envelopes:
        config:
          prefix: x/search_recent_tweets/ai_llms
          key: 2026-06-30T12:00:00_ai_llms.json
          persist: true
"""

import posixpath

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_marketplace.applications.x import (
    ABIModule,
    XSearchRecentTweetsEventConfiguration,
)
from naas_abi_marketplace.applications.x.orchestrations.utils import (
    launchpad_override,
    run_search_pipeline_for_file,
    safe_name,
)

# The XSearchRecentTweetsWorkflow / XIntegration write their query envelopes to
# ``<datastore_path>/search_recent_tweets/<slug>/<ts>_<slug>.json`` and the
# ObjectStorageService strips the leading ``storage/`` before publishing the
# ObjectPut event, so the event's ``prefix`` starts with the configured watched
# prefix (``search_recent_tweets_event[].prefix``, default ``x/search_recent_tweets``).
_TWEET_FILE_EXTENSIONS = (".json", ".ndjson", ".json.gz", ".ndjson.gz")

_PIPELINE_CONFIG_SCHEMA = {
    "prefix": dg.Field(
        str,
        description="Object-storage prefix of the search envelope.",
    ),
    "key": dg.Field(
        str,
        description="Object key of the search envelope under prefix.",
    ),
    "persist": dg.Field(
        bool,
        is_required=False,
        description="Persist mapped triples to the triple store.",
    ),
    "graph_name": dg.Field(
        str,
        is_required=False,
        description="Named graph IRI for mapped triples (ABI config default).",
    ),
}


def _is_search_recent_tweets_put(
    prefix: str, key: str, size_bytes: int | None, watched_prefix: str
) -> bool:
    """True when an ObjectPut targets a tweet envelope under *watched_prefix*."""
    if size_bytes is not None and size_bytes <= 0:
        return False
    if not key:
        return False
    normalized = prefix.strip("/")
    watched = watched_prefix.strip("/")
    if not (normalized == watched or normalized.startswith(watched + "/")):
        return False
    return key.lower().endswith(_TWEET_FILE_EXTENSIONS)


def _map_search_envelope(
    op_cfg: dict, event_cfg: XSearchRecentTweetsEventConfiguration
) -> None:
    """Map one persisted search envelope into the graph via the search pipeline."""
    module = ABIModule.get_instance()
    prefix = op_cfg["prefix"]
    key = op_cfg["key"]
    file_path = posixpath.join(prefix, key)

    logger.info(
        f"XSearchRecentTweetsEventOrchestration[{event_cfg.name}]: mapping "
        f"search_recent_tweets envelope {file_path} via XSearchRecentTweetsPipeline"
    )
    run_search_pipeline_for_file(
        file_path,
        persist=launchpad_override(op_cfg, "persist", event_cfg.persist),
        graph_name=launchpad_override(
            op_cfg, "graph_name", module.configuration.graph_name
        ),
    )


def _build_search_recent_tweets_event_sensor(
    event_cfg: XSearchRecentTweetsEventConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    """Build the (job, sensor) pair that maps search_recent_tweets envelopes
    for *event_cfg*.

    Job-per-entry so each sensor (which binds to a single job) and its durable
    event consumer are isolated. The sensor drains undelivered ``ObjectPut``
    events via ``events.query_for_consumer`` (durable cursor keyed on the sensor
    name — every put is seen exactly once), keeps only those landing under
    ``event_cfg.prefix``, and emits one RunRequest per file. The job is a single
    op that feeds that envelope's ``prefix/key`` path to
    :class:`XSearchRecentTweetsPipeline` in ``file_path`` mode, mapping the full
    SearchQuery / SearchResultSet / SearchRecentTweets / Tweet structure from the
    same file the workflow wrote (label-based dedupe makes a redelivered or
    re-put file a no-op). Same in-process executor argument as the other X jobs:
    share the dagster code-server's warm engine instead of forking a subprocess
    that re-bootstraps and races the api on oxigraph / nexus.db.
    """

    safe = safe_name(event_cfg.name)
    job_name = f"x_search_recent_tweets_ingestion_{safe}"
    pipeline_op_name = f"x_search_recent_tweets_pipeline_op_{safe}"
    sensor_name = f"x_search_recent_tweets_put_sensor_{safe}"

    @dg.op(name=pipeline_op_name, config_schema=_PIPELINE_CONFIG_SCHEMA)
    def search_pipeline_op(context) -> None:
        _map_search_envelope(context.op_config or {}, event_cfg)

    @dg.job(name=job_name, executor_def=dg.in_process_executor)
    def search_ingestion_job():
        search_pipeline_op()

    @dg.sensor(
        name=sensor_name,
        description=(
            f"Subscribe to ObjectPut events on the bus and map tweet envelopes "
            f"for filter '{event_cfg.name}' via XSearchRecentTweetsPipeline — "
            f"every new object written under {event_cfg.prefix!r} (the "
            f"search_recent_tweets envelopes). Event-driven — no polling of "
            f"object storage; each put is processed exactly once via the "
            f"durable consumer cursor."
        ),
        job=search_ingestion_job,
        minimum_interval_seconds=event_cfg.interval_seconds,
        default_status=(
            dg.DefaultSensorStatus.RUNNING
            if event_cfg.enabled
            else dg.DefaultSensorStatus.STOPPED
        ),
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
                consumer_id=sensor_name,
                event_class=ObjectPut,
                limit=event_cfg.events_per_tick,
                # Push the watched-prefix filter into the query so the per-tick
                # budget and the durable cursor only advance over puts under
                # this entry's prefix. `_is_search_recent_tweets_put` below
                # stays the authoritative check (exact prefix boundary, file
                # extension, non-empty size).
                filter={"prefix": {"prefix": event_cfg.prefix}},
            )
        except Exception as exc:  # noqa: BLE001
            return dg.SkipReason(
                f"ObjectPut event query failed ({exc}); will retry next tick"
            )

        if not new_events:
            return dg.SkipReason("no new ObjectPut events")

        object_storage = module.engine.services.object_storage
        run_requests: list[dg.RunRequest] = []
        for evt in new_events:
            prefix = evt.prefix or ""
            key = evt.key or ""
            if not _is_search_recent_tweets_put(
                prefix, key, evt.size_bytes, event_cfg.prefix
            ):
                continue
            # The ObjectPut event is a durable record of a *past* write; the
            # envelope may since have been deleted. Probe storage and skip stale
            # events here so we don't enqueue a run the pipeline op would only
            # fail on a missing object.
            try:
                object_storage.get_object_metadata(prefix, key)
            except Exceptions.ObjectNotFound:
                logger.info(
                    f"XSearchRecentTweetsEventOrchestration[{event_cfg.name}]: "
                    f"skipping ObjectPut for {prefix}/{key}; object no longer "
                    f"exists in storage"
                )
                continue
            run_requests.append(
                dg.RunRequest(
                    # Run-key includes prefix+key so the same envelope can't be
                    # double-enqueued and dagster's history shows which file
                    # each run handled.
                    run_key=f"{job_name}:{prefix}:{key}",
                    run_config={
                        "ops": {
                            pipeline_op_name: {
                                "config": {"prefix": prefix, "key": key}
                            }
                        }
                    },
                )
            )

        if not run_requests:
            return dg.SkipReason(
                f"{len(new_events)} ObjectPut event(s) processed; none landed "
                f"under {event_cfg.prefix!r}"
            )
        return run_requests

    return search_ingestion_job, search_ingestion_sensor


class XSearchRecentTweetsEventOrchestration(DagsterOrchestration):
    """One event-driven (job, sensor) pair per configured
    ``search_recent_tweets_event`` entry, each subscribing to ``ObjectPut``
    events and mapping every new envelope written under the entry's ``prefix``
    into the graph via :class:`XSearchRecentTweetsPipeline`. Sensors disabled by
    default unless ``enabled: true``.

    Launchpad example (manual replay of one envelope, filter ``search_envelopes``)::

        ops:
          x_search_recent_tweets_pipeline_op_search_envelopes:
            config:
              prefix: x/search_recent_tweets/my_filter
              key: 2026-06-30T12:00:00_my_filter.json
    """

    @classmethod
    def New(cls) -> "XSearchRecentTweetsEventOrchestration":
        module = ABIModule.get_instance()

        jobs: list[dg.JobDefinition] = []
        sensors: list[dg.SensorDefinition] = []

        seen_names: set[str] = set()
        for event_cfg in module.configuration.search_recent_tweets_event:
            if event_cfg.name in seen_names:
                logger.warning(
                    f"XSearchRecentTweetsEventOrchestration: duplicate "
                    f"search_recent_tweets_event name {event_cfg.name!r}; "
                    f"skipping the duplicate"
                )
                continue
            seen_names.add(event_cfg.name)
            job, sensor = _build_search_recent_tweets_event_sensor(event_cfg)
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

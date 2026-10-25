"""Files-reprocessing orchestration for the X application.

One (job, trigger) pair per ``search_recent_tweets_files`` config entry — a
**sensor** when the entry sets ``interval_seconds`` (elapsed-time cadence) or a
**schedule** when it sets ``cron`` (wall-clock times, UTC). Unless a previous
run is still in flight, the trigger starts a job that runs the tweet mapping
pipeline over the persisted search envelopes under that entry's ``prefix``.
Launch the job manually from the Dagster launchpad to override ``prefix`` /
``persist`` / ``skip_existing`` / ``max_age_hours`` / ``graph_name`` per run.

Unlike :class:`XSearchRecentTweetsEventOrchestration` (which maps one envelope
per ObjectPut event as files land), this orchestration sweeps **all** files
under a prefix in one run — a **fallback** when event ingestion missed puts.
It maps the graph, syncs namespace ``x`` datasets for successfully processed
paths, and republishes the app only when ``app_publish`` is on and at least one
file was mapped this sweep.

Skip-existing: before reprocessing, the job lists the folder, queries the graph
for the ``x:file_path`` of every ``x:SearchResultSet`` already mapped, and feeds
only the envelopes whose path is **not** yet in the graph to
:class:`XSearchRecentTweetsPipeline` in ``file_path`` mode (via the shared
``run_search_pipeline_for_file`` helper). Envelopes already in the graph but
missing from ``envelopes_v1`` are **not** remapped; they are synced to Dataset
Service on this sweep instead. Set ``skip_existing: false`` to force a full
re-run over every file (the pipeline's label-based dedupe still makes a re-run a
no-op).

``max_age_hours`` (optional) further limits the sweep to envelopes whose
filename timestamp (``<iso-ts>_<slug>.json``) falls within the last N hours.
Age filtering runs while listing keys, then again as a second filename pass.

All triggers start **RUNNING** by default; stop them from the Dagster UI when
needed.

Launchpad example (for an entry named ``reprocess_envelopes``)::

    ops:
      x_reprocess_recent_tweets_files_op_reprocess_envelopes:
        config:
          prefix: x/search_recent_tweets/ai_llms
          persist: true
          skip_existing: true
          max_age_hours: 24
          graph_name: http://ontology.naas.ai/graph/x
"""

import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import (
    ABIModule,
    XSearchRecentTweetsFilesConfiguration,
)
from naas_abi_marketplace.applications.x.flows import envelopes as _envelopes
from naas_abi_marketplace.applications.x.orchestrations.utils import (
    has_in_progress_run,
    launchpad_override,
    republish_x_app_after_pipeline,
    run_search_pipeline_for_file,
    safe_name,
)
from naas_abi_marketplace.applications.x.orchestrations.utils._common import (
    envelope_paths_in_dataset,
    normalize_envelope_path,
    sync_x_dataset_paths_batched,
)

_REPROCESS_MAX_RUNTIME_SECONDS = 5 * 60
_DATASET_PROBE_PROGRESS_EVERY = 25
T = TypeVar("T")

# The listing helpers moved to ``flows/envelopes.py`` (no Dagster there, so the
# durable reprocess flow can use them); the old names stay for this module's code
# and its tests.
_ENVELOPE_EXTENSIONS = _envelopes.ENVELOPE_EXTENSIONS
_ENVELOPE_TS_RE = _envelopes.ENVELOPE_TS_RE
_ListEnvelopeProgress = _envelopes.ListEnvelopeProgress
_envelope_path_timestamp = _envelopes.envelope_path_timestamp
_filter_dir_envelopes_by_cutoff = _envelopes.filter_dir_envelopes_by_cutoff
_filter_paths_by_max_age = _envelopes.filter_paths_by_max_age
_full_object_path = _envelopes.full_object_path
_list_envelope_paths = _envelopes.list_envelope_paths
_list_envelope_paths_within_cutoff = _envelopes.list_envelope_paths_within_cutoff
_list_envelopes_in_prefix_dir = _envelopes.list_envelopes_in_prefix_dir
_mapped_file_paths = _envelopes.mapped_file_paths
_path_is_envelope = _envelopes.path_is_envelope
_reprocess_log = _envelopes.reprocess_log
_within_max_age = _envelopes.within_max_age


class OrchestrationTimeoutError(TimeoutError):
    """Raised when file reprocessing exceeds its wall-clock time limit."""


def _with_signal_timeout(
    *,
    timeout_seconds: float,
    run_id: str,
    fn: Callable[[], T],
    log: Callable[[str], None] | None = None,
    config_name: str = "reprocess_envelopes",
) -> T:
    """Run ``fn`` under a SIGALRM wall-clock timeout (Linux/Unix only)."""
    if timeout_seconds <= 0:
        raise OrchestrationTimeoutError(
            f"X file reprocessing exceeded {timeout_seconds}s (run_id={run_id})."
        )
    if not hasattr(signal, "SIGALRM"):
        _reprocess_log(
            log,
            config_name=config_name,
            run_id=run_id,
            phase="timeout",
            message=(
                f"SIGALRM unavailable on this platform; "
                f"configured limit {timeout_seconds}s not enforced"
            ),
        )
        return fn()

    previous_handler = signal.getsignal(signal.SIGALRM)

    def _handler(_signum, _frame) -> None:  # pragma: no cover - raised by signal
        _reprocess_log(
            log,
            config_name=config_name,
            run_id=run_id,
            phase="timeout",
            message=f"SIGALRM fired after {timeout_seconds}s wall-clock limit",
        )
        raise OrchestrationTimeoutError(
            f"X file reprocessing exceeded {timeout_seconds}s (run_id={run_id})."
        )

    _reprocess_log(
        log,
        config_name=config_name,
        run_id=run_id,
        phase="timeout",
        message=f"arming SIGALRM wall-clock limit {timeout_seconds}s",
    )
    signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


_FILES_CONFIG_SCHEMA = {
    "prefix": dg.Field(
        str,
        is_required=False,
        description=(
            "Object-storage folder to reprocess (recursively). "
            "Defaults to the entry's configured prefix."
        ),
    ),
    "persist": dg.Field(
        bool,
        is_required=False,
        description="Persist mapped triples to the triple store.",
    ),
    "skip_existing": dg.Field(
        bool,
        is_required=False,
        description=(
            "Reprocess only envelopes whose path is not already the "
            "x:file_path of a mapped x:SearchResultSet (default true). "
            "Set false to force a full re-run over every file."
        ),
    ),
    "max_age_hours": dg.Field(
        int,
        is_required=False,
        description=(
            "Only reprocess envelopes whose filename timestamp is within "
            "the last N hours. Omit (or leave unset) for no age filter."
        ),
    ),
    "graph_name": dg.Field(
        str,
        is_required=False,
        description="Named graph IRI for mapped triples (ABI config default).",
    ),
    "app_publish": dg.Field(
        bool,
        is_required=False,
        description=(
            "After reprocessing, republish x/apps/x_proxy/ snapshots (+ web export). "
            "Defaults to the entry's configured app_publish (itself false "
            "unless set) — turn on here to force a rebuild for one run."
        ),
    ),
}


def _reprocess_files(
    config: XSearchRecentTweetsFilesConfiguration,
    op_cfg: dict | None = None,
    *,
    run_id: str = "unknown-run",
    log: Callable[[str], None] | None = None,
) -> dict:
    op_cfg = op_cfg or {}
    run_started = time.monotonic()
    module = ABIModule.get_instance()
    object_storage = module.engine.services.object_storage
    # Launchpad values win; otherwise fall back to this entry's config defaults.
    prefix = launchpad_override(op_cfg, "prefix", config.prefix)
    persist = launchpad_override(op_cfg, "persist", config.persist)
    skip_existing = launchpad_override(op_cfg, "skip_existing", config.skip_existing)
    max_age_hours = launchpad_override(op_cfg, "max_age_hours", config.max_age_hours)
    graph_name = launchpad_override(
        op_cfg, "graph_name", module.configuration.graph_name
    )

    # Shared cutoff so listing-time filter and the second filename pass agree.
    cutoff: datetime | None = None
    if max_age_hours is not None:
        cutoff = datetime.now(UTC) - timedelta(hours=int(max_age_hours))

    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="run",
        message=(
            f"started prefix={prefix!r} skip_existing={skip_existing} "
            f"max_age_hours={max_age_hours} persist={persist} graph_name={graph_name!r}"
        ),
    )

    list_started = time.monotonic()
    list_progress = _ListEnvelopeProgress(log, config.name, run_id)
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="list_envelopes",
        message=f"started prefix={prefix!r} max_age_hours={max_age_hours}",
    )
    paths, skipped_age = _list_envelope_paths(
        object_storage, prefix, cutoff=cutoff, progress=list_progress
    )
    list_progress.maybe_log_progress(force=True)
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="list_envelopes",
        message=(
            f"done elapsed={time.monotonic() - list_started:.2f}s "
            f"recent_envelopes={len(paths)} skipped_age={skipped_age}"
        ),
    )

    # Second filename-timestamp check (same rule) after listing.
    if cutoff is not None:
        recheck_started = time.monotonic()
        before = len(paths)
        paths, skipped_recheck = _filter_paths_by_max_age(paths, cutoff=cutoff)
        skipped_age += skipped_recheck
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="age_recheck",
            message=(
                f"done elapsed={time.monotonic() - recheck_started:.2f}s "
                f"before={before} after={len(paths)} skipped={skipped_recheck}"
            ),
        )

    # skip_existing: map only paths not in the graph; dataset-sync paths that are
    # in the graph but missing from envelopes_v1 (same gap as ObjectPut Events).
    paths_dataset_only: list[str] = []
    skipped_fully_projected = 0
    if skip_existing:
        mapped_started = time.monotonic()
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="mapped_paths_query",
            message=f"started graph_name={graph_name!r}",
        )
        mapped = _mapped_file_paths(
            module.engine.services.triple_store,
            graph_name,
            module.configuration.ontology_namespace,
        )
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="mapped_paths_query",
            message=(
                f"done elapsed={time.monotonic() - mapped_started:.2f}s "
                f"mapped_paths={len(mapped)}"
            ),
        )

        probe_started = time.monotonic()
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="dataset_projection_probe",
            message=f"started candidates={len(paths)} bulk_lookup=true",
        )
        ingested_in_dataset = envelope_paths_in_dataset(module, paths)
        to_map: list[str] = []
        for index, path in enumerate(paths, start=1):
            normalized = normalize_envelope_path(path)
            if path not in mapped:
                to_map.append(path)
            elif normalized in ingested_in_dataset:
                skipped_fully_projected += 1
            else:
                paths_dataset_only.append(path)
            if index == len(paths) or index % _DATASET_PROBE_PROGRESS_EVERY == 0:
                _reprocess_log(
                    log,
                    config_name=config.name,
                    run_id=run_id,
                    phase="dataset_projection_probe",
                    message=(
                        f"progress {index}/{len(paths)} elapsed="
                        f"{time.monotonic() - probe_started:.1f}s "
                        f"to_map={len(to_map)} fully_projected={skipped_fully_projected} "
                        f"dataset_only={len(paths_dataset_only)} "
                        f"ingested_in_dataset={len(ingested_in_dataset)}"
                    ),
                )
        paths = to_map
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="dataset_projection_probe",
            message=(
                f"done elapsed={time.monotonic() - probe_started:.2f}s "
                f"to_map={len(paths)} fully_projected={skipped_fully_projected} "
                f"dataset_only={len(paths_dataset_only)}"
            ),
        )

    age_note = (
        f", {skipped_age} older than {max_age_hours}h skipped" if max_age_hours else ""
    )
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="plan",
        message=(
            f"{len(paths)} envelope(s) under {prefix!r} to map via "
            f"XSearchRecentTweetsPipeline ({skipped_fully_projected} fully projected "
            f"skipped, {len(paths_dataset_only)} dataset-only catch-up{age_note})"
        ),
    )

    processed = 0
    failed = 0
    processed_paths: list[str] = []
    map_started = time.monotonic()
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="map_envelopes",
        message=f"started count={len(paths)}",
    )
    for index, file_path in enumerate(paths, start=1):
        file_started = time.monotonic()
        try:
            run_search_pipeline_for_file(
                file_path, persist=persist, graph_name=graph_name
            )
            processed += 1
            processed_paths.append(file_path)
            _reprocess_log(
                log,
                config_name=config.name,
                run_id=run_id,
                phase="map_envelopes",
                message=(
                    f"mapped {index}/{len(paths)} elapsed="
                    f"{time.monotonic() - file_started:.2f}s path={file_path!r}"
                ),
            )
        except OrchestrationTimeoutError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Don't let one bad envelope abort the whole reprocess run.
            failed += 1
            _reprocess_log(
                log,
                config_name=config.name,
                run_id=run_id,
                phase="map_envelopes",
                message=(
                    f"failed {index}/{len(paths)} path={file_path!r} ({exc}); "
                    f"continuing"
                ),
            )
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="map_envelopes",
        message=(
            f"done elapsed={time.monotonic() - map_started:.2f}s "
            f"processed={processed} failed={failed}"
        ),
    )

    dataset_paths = processed_paths + paths_dataset_only
    summary = {
        "prefix": prefix,
        "processed": processed,
        "skipped": skipped_fully_projected,
        "dataset_only": len(paths_dataset_only),
        "skipped_age": skipped_age,
        "max_age_hours": max_age_hours,
        "failed": failed,
    }
    # Fallback when ObjectPut ingestion missed envelopes: graph + dataset for
    # every path mapped this sweep, plus dataset-only catch-up for graph-mapped
    # paths missing from envelopes_v1.
    if dataset_paths:
        sync_started = time.monotonic()
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="dataset_sync",
            message=f"started paths={len(dataset_paths)} batch_size=64",
        )
        summary["dataset"] = sync_x_dataset_paths_batched(
            module, dataset_paths, batch_size=64
        )
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="dataset_sync",
            message=(
                f"done elapsed={time.monotonic() - sync_started:.2f}s "
                f"summary={summary['dataset']}"
            ),
        )
    else:
        summary["dataset"] = {"skipped": True, "reason": "no_paths_to_sync"}
        _reprocess_log(
            log,
            config_name=config.name,
            run_id=run_id,
            phase="dataset_sync",
            message="skipped (no paths to sync)",
        )
    # Republish static app snapshots only when this sweep actually mapped
    # something (same gate as primary event path, but optional via app_publish).
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="app_publish",
        message="started",
    )
    summary["app"] = republish_x_app_after_pipeline(
        module,
        source=f"XSearchRecentTweetsFilesOrchestration[{config.name}]",
        app_publish=launchpad_override(op_cfg, "app_publish", config.app_publish),
        ran=processed > 0,
    )
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="app_publish",
        message=f"done result={summary['app']}",
    )
    _reprocess_log(
        log,
        config_name=config.name,
        run_id=run_id,
        phase="run",
        message=(
            f"done elapsed={time.monotonic() - run_started:.2f}s summary={summary}"
        ),
    )
    return summary


def _trigger_description(config: XSearchRecentTweetsFilesConfiguration) -> str:
    """Human-readable summary shown on the entry's sensor / schedule."""
    cadence = (
        f"on cron '{config.cron}' (UTC)"
        if config.cron
        else f"every {config.interval_seconds}s"
    )
    age_note = (
        f", limited to the last {config.max_age_hours}h" if config.max_age_hours else ""
    )
    return (
        f"Reprocess persisted search_recent_tweets envelopes for filter "
        f"'{config.name}' {cadence}: list {config.prefix!r}{age_note}, skip every "
        f"file already mapped as the x:file_path of an x:SearchResultSet, and "
        f"feed the rest to XSearchRecentTweetsPipeline."
    )


def _default_files_run_config(
    entry_config: XSearchRecentTweetsFilesConfiguration,
) -> dict:
    """Launchpad defaults for one files-reprocess job (single op, step 1)."""
    safe = safe_name(entry_config.name)
    op_name = f"x_reprocess_recent_tweets_files_op_{safe}"
    body: dict[str, object] = {
        "prefix": entry_config.prefix,
        "persist": entry_config.persist,
        "skip_existing": entry_config.skip_existing,
        "app_publish": entry_config.app_publish,
    }
    if entry_config.max_age_hours is not None:
        body["max_age_hours"] = entry_config.max_age_hours
    return {"ops": {op_name: {"config": body}}}


def _build_reprocess_files_definitions(
    config: XSearchRecentTweetsFilesConfiguration,
) -> tuple[
    dg.JobDefinition,
    dg.SensorDefinition | None,
    dg.ScheduleDefinition | None,
]:
    """Build the (job, trigger) pair that reprocesses the envelopes under
    *config*'s ``prefix``.

    Job-per-entry so each trigger (which binds to a single job) throttles
    independently. The job is a single op that sweeps the folder and feeds the
    not-yet-mapped envelopes to :class:`XSearchRecentTweetsPipeline` in
    ``file_path`` mode. Same in-process executor argument as the other X jobs:
    share the dagster code-server's warm engine instead of forking a subprocess
    that re-bootstraps and races the api on oxigraph / nexus.db.

    Exactly one of the returned trigger slots is populated: a sensor for an
    ``interval_seconds`` entry, a schedule for a ``cron`` one (the config model
    rejects entries that set both).
    """

    safe = safe_name(config.name)
    job_name = f"x_reprocess_recent_tweets_files_{safe}"
    op_name = f"x_reprocess_recent_tweets_files_op_{safe}"
    sensor_name = f"x_reprocess_recent_tweets_files_sensor_{safe}"
    schedule_name = f"x_reprocess_recent_tweets_files_schedule_{safe}"
    description = _trigger_description(config)

    @dg.op(name=op_name, config_schema=_FILES_CONFIG_SCHEMA)
    def reprocess_files_op(context) -> dict:
        run_id = str(getattr(context, "run_id", "unknown-run"))
        op_log = context.log.info

        def _run() -> dict:
            return _reprocess_files(
                config,
                context.op_config or {},
                run_id=run_id,
                log=op_log,
            )

        return _with_signal_timeout(
            timeout_seconds=_REPROCESS_MAX_RUNTIME_SECONDS,
            run_id=run_id,
            fn=_run,
            log=op_log,
            config_name=config.name,
        )

    @dg.job(
        name=job_name,
        executor_def=dg.in_process_executor,
        config=_default_files_run_config(config),
    )
    def reprocess_files_job():
        reprocess_files_op()

    if config.cron:

        @dg.schedule(
            name=schedule_name,
            description=description,
            job=reprocess_files_job,
            cron_schedule=config.cron,
            execution_timezone="UTC",
            default_status=dg.DefaultScheduleStatus.RUNNING,
        )
        def reprocess_files_schedule(context: dg.ScheduleEvaluationContext):
            if has_in_progress_run(context, job_name):
                return dg.SkipReason(f"Job '{job_name}' is already running.")
            return [dg.RunRequest(run_key=None)]

        return reprocess_files_job, None, reprocess_files_schedule

    @dg.sensor(
        name=sensor_name,
        description=description,
        job=reprocess_files_job,
        minimum_interval_seconds=config.interval_seconds,
        default_status=dg.DefaultSensorStatus.RUNNING,
    )
    def reprocess_files_sensor(context: dg.SensorEvaluationContext):
        # One reprocess run at a time: a sweep can outlast the tick, so skip
        # rather than stack overlapping runs over the same folder.
        if has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")
        return [dg.RunRequest(run_key=None)]

    return reprocess_files_job, reprocess_files_sensor, None


class XSearchRecentTweetsFilesOrchestration(DagsterOrchestration):
    """One (job, trigger) pair per configured ``search_recent_tweets_files``
    entry — driven by a sensor (``interval_seconds``) or a schedule (``cron``)
    — each sweeping the persisted search envelopes under the entry's ``prefix``
    and reprocessing only the files not yet mapped into the graph via
    :class:`XSearchRecentTweetsPipeline`. Triggers start RUNNING by default.

    Launchpad example (replace ``reprocess_envelopes`` with your entry name)::

        ops:
          x_reprocess_recent_tweets_files_op_reprocess_envelopes:
            config:
              prefix: x/search_recent_tweets
              skip_existing: true
              max_age_hours: 24
    """

    @classmethod
    def New(cls) -> "XSearchRecentTweetsFilesOrchestration":
        module = ABIModule.get_instance()

        jobs: list[dg.JobDefinition] = []
        sensors: list[dg.SensorDefinition] = []
        schedules: list[dg.ScheduleDefinition] = []

        seen_names: set[str] = set()
        for files_config in module.configuration.search_recent_tweets_files:
            if files_config.name in seen_names:
                logger.warning(
                    f"XSearchRecentTweetsFilesOrchestration: duplicate "
                    f"search_recent_tweets_files name {files_config.name!r}; "
                    f"skipping the duplicate"
                )
                continue
            seen_names.add(files_config.name)
            job, sensor, schedule = _build_reprocess_files_definitions(files_config)
            jobs.append(job)
            if sensor is not None:
                sensors.append(sensor)
            if schedule is not None:
                schedules.append(schedule)

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=schedules,
                jobs=jobs,
                sensors=sensors,
            )
        )

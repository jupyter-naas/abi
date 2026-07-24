"""Files-reprocessing orchestration for the X application.

One (job, sensor) pair per ``search_recent_tweets_files`` config entry. Each
sensor wakes every ``interval_seconds`` (default 5400 — every 1 h 30 min) and,
unless a previous run is still in flight, triggers a job that runs the tweet
mapping pipeline over the persisted search envelopes under that entry's
``prefix``. Launch the job manually from the Dagster launchpad to override
``prefix`` / ``persist`` / ``skip_existing`` / ``max_age_hours`` / ``graph_name``
per run.

Unlike :class:`XSearchRecentTweetsEventOrchestration` (which maps one envelope
per ObjectPut event as files land), this orchestration sweeps **all** files
under a prefix in one run. Use it to backfill / re-ingest the graph after a
mapping change without re-querying the X API.

Skip-existing: before reprocessing, the job lists the folder, queries the graph
for the ``x:file_path`` of every ``x:SearchResultSet`` already mapped, and feeds
only the envelopes whose path is **not** yet in the graph to
:class:`XSearchRecentTweetsPipeline` in ``file_path`` mode (via the shared
``run_search_pipeline_for_file`` helper). That rebuilds the full SearchQuery /
SearchResultSet / SearchRecentTweets / Tweet structure from each new file. Set
``skip_existing: false`` to force a full re-run over every file (the pipeline's
label-based dedupe still makes a re-run a no-op).

``max_age_hours`` (optional) further limits the sweep to envelopes whose
filename timestamp (``<iso-ts>_<slug>.json``) falls within the last N hours.
Age filtering runs while listing keys, then again as a second filename pass.

All sensors are **disabled by default** (``DefaultSensorStatus.STOPPED``); set
``enabled: true`` on an entry to create its sensor RUNNING, or enable it from
the Dagster UI.

Launchpad example (for an entry named ``reprocess_envelopes``)::

    ops:
      x_search_recent_tweets_files_op_reprocess_envelopes:
        config:
          prefix: x/search_recent_tweets/ai_llms
          persist: true
          skip_existing: true
          max_age_hours: 24
          graph_name: http://ontology.naas.ai/graph/x
"""

import posixpath
import re
from datetime import datetime, timedelta, timezone

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import (
    ABIModule,
    XSearchRecentTweetsFilesConfiguration,
)
from naas_abi_marketplace.applications.x.orchestrations.utils import (
    has_in_progress_run,
    launchpad_override,
    run_search_pipeline_for_file,
    safe_name,
)

_ENVELOPE_EXTENSIONS = (".json", ".ndjson", ".json.gz", ".ndjson.gz")
# ``2026-07-23T15:46:04.705264+00:00_<slug>.json`` or underscored older form
# ``2026-06-29T17_58_45.974146+00_00_<slug>.json``.
_ENVELOPE_TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T[\d_:.+-]+?)_")

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
}


def _envelope_path_timestamp(file_path: str) -> datetime | None:
    """Parse the leading ISO (or underscored-ISO) timestamp from an envelope key.

    Returns an aware UTC datetime, or ``None`` when the basename does not match
    the ``<ts>_<slug>.json`` convention.
    """
    name = posixpath.basename(file_path)
    match = _ENVELOPE_TS_RE.match(name)
    if not match:
        return None
    stamp = match.group("ts")
    # Older files used underscores in the time / offset: ``T17_58_45…+00_00``.
    if "+00_00" in stamp or (stamp.count("_") >= 2 and "T" in stamp):
        try:
            date, rest = stamp.split("T", 1)
            if "+" not in rest:
                return None
            time_part, tz = rest.rsplit("+", 1)
            parsed = datetime.fromisoformat(
                f"{date}T{time_part.replace('_', ':')}+{tz.replace('_', ':')}"
            )
        except ValueError:
            return None
    else:
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _within_max_age(file_path: str, cutoff: datetime) -> bool:
    """True iff *file_path*'s filename timestamp is parseable and ``>= cutoff``."""
    ts = _envelope_path_timestamp(file_path)
    return ts is not None and ts >= cutoff


def _list_envelope_paths(
    object_storage,
    prefix: str,
    *,
    cutoff: datetime | None = None,
    _seen: set[str] | None = None,
) -> tuple[list[str], int]:
    """Full object-storage paths of every envelope file under *prefix*.

    ``list_objects`` is depth-1 only (direct children). Envelopes live under
    ``<prefix>/<slug>/<ts>_<slug>.json``, so this walks into subdirectory
    children (S3 common-prefixes ending in ``/``, or FS directory names)
    until it finds JSON envelope files. Returned paths are the full
    ``prefix/…/file`` keys the pipeline's ``file_path`` mode expects.

    When *cutoff* is set, each envelope key is age-checked from its filename
    timestamp **while listing** (older / unparseable keys are dropped and
    counted in the returned skip total). Callers that set *cutoff* should still
    run :func:`_filter_paths_by_max_age` as a second filename pass.
    """
    prefix = prefix.rstrip("/")
    seen = _seen if _seen is not None else set()
    if not prefix or prefix in seen:
        return [], 0
    seen.add(prefix)

    try:
        all_keys = object_storage.list_objects(prefix) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XSearchRecentTweetsFilesOrchestration: list_objects({prefix!r}) "
            f"failed ({exc})"
        )
        return [], 0

    paths: list[str] = []
    skipped_age = 0
    for k in all_keys:
        if not k:
            continue
        full_path = k if k.startswith(prefix) else posixpath.join(prefix, k)
        base = posixpath.basename(full_path.rstrip("/"))
        # Nexus folder markers are zero-byte placeholders, not real prefixes.
        if base == ".nexus_folder":
            continue
        if full_path.endswith("/"):
            child_paths, child_skipped = _list_envelope_paths(
                object_storage,
                full_path.rstrip("/"),
                cutoff=cutoff,
                _seen=seen,
            )
            paths.extend(child_paths)
            skipped_age += child_skipped
            continue
        if full_path.lower().endswith(_ENVELOPE_EXTENSIONS):
            if cutoff is not None and not _within_max_age(full_path, cutoff):
                skipped_age += 1
                continue
            paths.append(full_path)
            continue
        # Non-envelope child with no trailing slash — likely a slug dir (FS
        # adapter) or an unrelated file. Recurse; empty/missing dirs no-op.
        child_paths, child_skipped = _list_envelope_paths(
            object_storage, full_path, cutoff=cutoff, _seen=seen
        )
        paths.extend(child_paths)
        skipped_age += child_skipped
    return paths, skipped_age


def _filter_paths_by_max_age(
    paths: list[str],
    *,
    cutoff: datetime,
) -> tuple[list[str], int]:
    """Second-pass filename age filter (same rule as listing-time check).

    Paths with unparseable timestamps or ``ts < cutoff`` are dropped. Kept even
    after listing already filtered, as a safety net against key-shape edge cases.
    """
    kept: list[str] = []
    skipped = 0
    for path in paths:
        if not _within_max_age(path, cutoff):
            skipped += 1
            continue
        kept.append(path)
    return kept, skipped


def _mapped_file_paths(triple_store, graph_name: str, namespace: str) -> set[str]:
    """Every ``x:file_path`` already recorded on an ``x:SearchResultSet``.

    A SPARQL SELECT against the configured named graph for the file paths of
    the result sets already mapped — the set of envelopes we can skip on a
    reprocess run. The ``x:file_path`` the pipeline stores is exactly the
    ``prefix/key`` path produced by :func:`_list_envelope_paths`, so the
    returned strings are directly comparable.
    """
    class_uri = f"{namespace}SearchResultSet"
    prop_uri = f"{namespace}file_path"
    sparql = (
        f"SELECT DISTINCT ?fp WHERE {{ GRAPH <{graph_name}> {{ "
        f"?s a <{class_uri}> ; <{prop_uri}> ?fp . }} }}"
    )
    try:
        result = triple_store.query(sparql)
    except Exception as exc:  # noqa: BLE001
        # Fail open: if the graph can't be queried, fall back to reprocessing
        # everything (the pipeline's label-based dedupe still no-ops re-runs)
        # rather than silently skipping files we couldn't confirm are mapped.
        logger.warning(
            f"XSearchRecentTweetsFilesOrchestration: SearchResultSet file_path "
            f"query failed ({exc}); treating all files as not-yet-mapped"
        )
        return set()
    return {str(row.fp) for row in result if getattr(row, "fp", None) is not None}


def _reprocess_files(
    config: XSearchRecentTweetsFilesConfiguration,
    op_cfg: dict | None = None,
) -> dict:
    op_cfg = op_cfg or {}
    module = ABIModule.get_instance()
    object_storage = module.engine.services.object_storage
    # Launchpad values win; otherwise fall back to this entry's config defaults.
    prefix = launchpad_override(op_cfg, "prefix", config.prefix)
    persist = launchpad_override(op_cfg, "persist", config.persist)
    skip_existing = launchpad_override(op_cfg, "skip_existing", config.skip_existing)
    max_age_hours = launchpad_override(
        op_cfg, "max_age_hours", config.max_age_hours
    )
    graph_name = launchpad_override(
        op_cfg, "graph_name", module.configuration.graph_name
    )

    # Shared cutoff so listing-time filter and the second filename pass agree.
    cutoff: datetime | None = None
    if max_age_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=int(max_age_hours))

    paths, skipped_age = _list_envelope_paths(
        object_storage, prefix, cutoff=cutoff
    )
    # Second filename-timestamp check (same rule) after listing.
    if cutoff is not None:
        paths, skipped_recheck = _filter_paths_by_max_age(paths, cutoff=cutoff)
        skipped_age += skipped_recheck

    # Reprocess only files not already in the graph: drop every path that is the
    # x:file_path of an x:SearchResultSet already mapped into graph_name.
    skipped = 0
    if skip_existing:
        mapped = _mapped_file_paths(
            module.engine.services.triple_store,
            graph_name,
            module.configuration.ontology_namespace,
        )
        before = len(paths)
        paths = [p for p in paths if p not in mapped]
        skipped = before - len(paths)

    age_note = (
        f", {skipped_age} older than {max_age_hours}h skipped"
        if max_age_hours
        else ""
    )
    logger.info(
        f"XSearchRecentTweetsFilesOrchestration[{config.name}]: {len(paths)} "
        f"envelope(s) under {prefix!r} to reprocess via "
        f"XSearchRecentTweetsPipeline ({skipped} already in graph skipped"
        f"{age_note})"
    )

    processed = 0
    failed = 0
    for file_path in paths:
        try:
            run_search_pipeline_for_file(
                file_path, persist=persist, graph_name=graph_name
            )
            processed += 1
        except Exception as exc:  # noqa: BLE001
            # Don't let one bad envelope abort the whole reprocess run.
            failed += 1
            logger.warning(
                f"XSearchRecentTweetsFilesOrchestration[{config.name}]: failed to "
                f"reprocess {file_path!r} ({exc}); continuing"
            )

    summary = {
        "prefix": prefix,
        "processed": processed,
        "skipped": skipped,
        "skipped_age": skipped_age,
        "max_age_hours": max_age_hours,
        "failed": failed,
    }
    logger.info(
        f"XSearchRecentTweetsFilesOrchestration[{config.name}]: done — {summary}"
    )
    return summary


def _build_reprocess_files_job_sensor(
    config: XSearchRecentTweetsFilesConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    """Build the (job, sensor) pair that reprocesses the envelopes under
    *config*'s ``prefix``.

    Job-per-entry so each sensor (which binds to a single job) throttles
    independently. The job is a single op that sweeps the folder and feeds the
    not-yet-mapped envelopes to :class:`XSearchRecentTweetsPipeline` in
    ``file_path`` mode. Same in-process executor argument as the other X jobs:
    share the dagster code-server's warm engine instead of forking a subprocess
    that re-bootstraps and races the api on oxigraph / nexus.db.
    """

    safe = safe_name(config.name)
    job_name = f"x_search_recent_tweets_files_{safe}"
    op_name = f"x_search_recent_tweets_files_op_{safe}"
    sensor_name = f"x_search_recent_tweets_files_sensor_{safe}"

    @dg.op(name=op_name, config_schema=_FILES_CONFIG_SCHEMA)
    def reprocess_files_op(context) -> dict:
        return _reprocess_files(config, context.op_config or {})

    @dg.job(name=job_name, executor_def=dg.in_process_executor)
    def reprocess_files_job():
        reprocess_files_op()

    age_note = (
        f", limited to the last {config.max_age_hours}h"
        if config.max_age_hours
        else ""
    )

    @dg.sensor(
        name=sensor_name,
        description=(
            f"Reprocess persisted search_recent_tweets envelopes for filter "
            f"'{config.name}' every {config.interval_seconds}s: list "
            f"{config.prefix!r}{age_note}, skip every file already mapped as the "
            f"x:file_path of an x:SearchResultSet, and feed the rest to "
            f"XSearchRecentTweetsPipeline."
        ),
        job=reprocess_files_job,
        minimum_interval_seconds=config.interval_seconds,
        default_status=(
            dg.DefaultSensorStatus.RUNNING
            if config.enabled
            else dg.DefaultSensorStatus.STOPPED
        ),
    )
    def reprocess_files_sensor(context: dg.SensorEvaluationContext):
        # One reprocess run at a time: a sweep can outlast the tick, so skip
        # rather than stack overlapping runs over the same folder.
        if has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")
        return [dg.RunRequest(run_key=None)]

    return reprocess_files_job, reprocess_files_sensor


class XSearchRecentTweetsFilesOrchestration(DagsterOrchestration):
    """One (job, sensor) pair per configured ``search_recent_tweets_files``
    entry, each sweeping the persisted search envelopes under the entry's
    ``prefix`` on a fixed cadence and reprocessing only the files not yet mapped
    into the graph via :class:`XSearchRecentTweetsPipeline`. Sensors disabled by
    default unless ``enabled: true``.

    Launchpad example (replace ``reprocess_envelopes`` with your entry name)::

        ops:
          x_search_recent_tweets_files_op_reprocess_envelopes:
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
            job, sensor = _build_reprocess_files_job_sensor(files_config)
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

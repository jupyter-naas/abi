"""Manual files-reprocessing orchestration for the X application.

A single job — **no sensor, no schedule, no X API call** — that runs the tweet
mapping pipeline over every persisted search envelope under a given
object-storage folder. Launch it from the Dagster launchpad and set ``prefix``
to pick the folder to reprocess (defaults to ``x/search_recent_tweets``).

Unlike :class:`XSearchRecentTweetsEventOrchestration` (which maps one envelope
per ObjectPut event as files land), this orchestration sweeps **all** files
under a prefix in one manual run. Use it to backfill / re-ingest the whole graph
after a mapping change without re-querying the X API.

Pipeline-only: each envelope is fed straight to
:class:`XSearchRecentTweetsPipeline` in ``file_path`` mode (via the shared
``run_search_pipeline_for_file`` helper), which rebuilds the full SearchQuery /
SearchResultSet / SearchRecentTweets / Tweet structure from the file.
Idempotent — the pipeline's label-based dedupe makes a re-run a no-op.

Launchpad example::

    ops:
      x_search_recent_tweets_files_op:
        config:
          prefix: x/search_recent_tweets/ai_llms
          persist: true
          graph_name: http://ontology.naas.ai/graph/x
"""

import posixpath

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.orchestrations.utils import (
    launchpad_override,
    run_search_pipeline_for_file,
)

# Default folder to reprocess: the envelopes the search workflow / integration
# persist. Override per-run from the Dagster launchpad to target another folder.
_DEFAULT_PREFIX = "x/search_recent_tweets"
_ENVELOPE_EXTENSIONS = (".json", ".ndjson", ".json.gz", ".ndjson.gz")

_JOB_NAME = "x_search_recent_tweets_files"
_OP_NAME = "x_search_recent_tweets_files_op"

_FILES_CONFIG_SCHEMA = {
    "prefix": dg.Field(
        str,
        is_required=False,
        description=(
            "Object-storage folder to reprocess (recursively). "
            f"Defaults to {_DEFAULT_PREFIX!r}."
        ),
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


def _list_envelope_paths(object_storage, prefix: str) -> list[str]:
    """Full object-storage paths of every envelope file under *prefix*.

    ``list_objects`` returns keys that may already include the prefix; normalise
    each back to a full ``prefix/key`` path (what the pipeline's ``file_path``
    mode expects) and keep only the JSON envelope extensions.
    """
    try:
        all_keys = object_storage.list_objects(prefix) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"XSearchRecentTweetsFilesOrchestration: list_objects({prefix!r}) "
            f"failed ({exc})"
        )
        return []

    paths: list[str] = []
    for k in all_keys:
        if not k or not k.lower().endswith(_ENVELOPE_EXTENSIONS):
            continue
        full_path = k if k.startswith(prefix) else posixpath.join(prefix, k)
        paths.append(full_path)
    return paths


def _reprocess_files(op_cfg: dict | None = None) -> dict:
    op_cfg = op_cfg or {}
    module = ABIModule.get_instance()
    object_storage = module.engine.services.object_storage
    prefix = launchpad_override(op_cfg, "prefix", _DEFAULT_PREFIX)
    persist = launchpad_override(op_cfg, "persist", True)
    graph_name = launchpad_override(
        op_cfg, "graph_name", module.configuration.graph_name
    )

    paths = _list_envelope_paths(object_storage, prefix)
    logger.info(
        f"XSearchRecentTweetsFilesOrchestration: {len(paths)} envelope(s) under "
        f"{prefix!r} to reprocess via XSearchRecentTweetsPipeline"
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
                f"XSearchRecentTweetsFilesOrchestration: failed to reprocess "
                f"{file_path!r} ({exc}); continuing"
            )

    summary = {"prefix": prefix, "processed": processed, "failed": failed}
    logger.info(f"XSearchRecentTweetsFilesOrchestration: done — {summary}")
    return summary


@dg.op(name=_OP_NAME, config_schema=_FILES_CONFIG_SCHEMA)
def reprocess_files_op(context) -> dict:
    return _reprocess_files(context.op_config or {})


# Single-op job, no schedule and no sensor → launch manually from the Dagster
# UI. In-process executor shares the code-server's warm engine (same rationale
# as the other X jobs) instead of forking a subprocess that re-bootstraps.
@dg.job(name=_JOB_NAME, executor_def=dg.in_process_executor)
def reprocess_files_job():
    reprocess_files_op()


class XSearchRecentTweetsFilesOrchestration(DagsterOrchestration):
    """Manually-triggered, pipeline-only reprocessing of every persisted search
    envelope under a configurable object-storage folder.

    Exposes a single job with no sensor/schedule, so it only runs when launched
    from the Dagster launchpad; set ``prefix`` (and optional ``persist`` /
    ``graph_name``) in the run config to tune the run.

    Launchpad example::

        ops:
          x_search_recent_tweets_files_op:
            config:
              prefix: x/search_recent_tweets
    """

    @classmethod
    def New(cls) -> "XSearchRecentTweetsFilesOrchestration":
        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=[reprocess_files_job],
                sensors=[],
            )
        )

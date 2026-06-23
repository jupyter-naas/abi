"""Manual reprocessing orchestration for the X application.

A single job — **no sensor, no schedule, no X API call** — that re-runs the
tweet mapping pipeline over every persisted search envelope under a given
object-storage folder. Launch it from the Dagster UI and set the ``prefix`` in
the run config to pick the folder to reprocess (defaults to the
``x/search_recent_tweets`` envelopes).

Pipeline-only: each envelope is fed straight to
:class:`XSearchRecentTweetsPipeline` in ``file_path`` mode (via the shared
``run_search_pipeline_for_file`` helper), which rebuilds the full SearchQuery /
SearchResultSet / SearchRecentTweets / Tweet structure from the file. Use it to
backfill the graph after a mapping change without re-querying the X API.
Idempotent — the pipeline's label-based dedupe makes a re-run a no-op.
"""

import posixpath

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.orchestrations.utils import (
    run_search_pipeline_for_file,
)

# Default folder to reprocess: the envelopes the search workflow / integration
# persist. Override per-run from the Dagster launchpad to target another folder.
_DEFAULT_PREFIX = "x/search_recent_tweets"
_ENVELOPE_EXTENSIONS = (".json", ".ndjson", ".json.gz", ".ndjson.gz")

_JOB_NAME = "x_reprocess_envelopes"
_OP_NAME = "x_reprocess_envelopes_op"


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
            f"XReprocessOrchestration: list_objects({prefix!r}) failed ({exc})"
        )
        return []

    paths: list[str] = []
    for k in all_keys:
        if not k or not k.lower().endswith(_ENVELOPE_EXTENSIONS):
            continue
        full_path = k if k.startswith(prefix) else posixpath.join(prefix, k)
        paths.append(full_path)
    return paths


@dg.op(
    name=_OP_NAME,
    config_schema={
        "prefix": dg.Field(
            str,
            default_value=_DEFAULT_PREFIX,
            description="Object-storage folder to reprocess (recursively).",
        )
    },
)
def reprocess_envelopes_op(context: dg.OpExecutionContext) -> dict:
    module = ABIModule.get_instance()
    object_storage = module.engine.services.object_storage
    prefix = context.op_config["prefix"]

    paths = _list_envelope_paths(object_storage, prefix)
    logger.info(
        f"XReprocessOrchestration: {len(paths)} envelope(s) under {prefix!r} to "
        f"reprocess via XSearchRecentTweetsPipeline"
    )

    processed = 0
    failed = 0
    for file_path in paths:
        try:
            run_search_pipeline_for_file(file_path)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            # Don't let one bad envelope abort the whole reprocess run.
            failed += 1
            logger.warning(
                f"XReprocessOrchestration: failed to reprocess {file_path!r} "
                f"({exc}); continuing"
            )

    summary = {"prefix": prefix, "processed": processed, "failed": failed}
    logger.info(f"XReprocessOrchestration: done — {summary}")
    return summary


# Single-op job, no schedule and no sensor → launch manually from the Dagster
# UI. In-process executor shares the code-server's warm engine (same rationale
# as the other X jobs) instead of forking a subprocess that re-bootstraps.
@dg.job(name=_JOB_NAME, executor_def=dg.in_process_executor)
def reprocess_envelopes_job():
    reprocess_envelopes_op()


class XReprocessOrchestration(DagsterOrchestration):
    """Manually-triggered, pipeline-only reprocessing of persisted search
    envelopes under a configurable object-storage folder.

    Exposes a single job with no sensor/schedule, so it only runs when launched
    from the Dagster UI; set ``prefix`` in the run config to choose the folder.
    """

    @classmethod
    def New(cls) -> "XReprocessOrchestration":
        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=[reprocess_envelopes_job],
                sensors=[],
            )
        )

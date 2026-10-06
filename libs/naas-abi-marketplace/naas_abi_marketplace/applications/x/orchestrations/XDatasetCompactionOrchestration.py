"""Scheduled DuckLake compaction of the X Dataset Service tables.

Each sync batch commits a snapshot and a few small Parquet files - during
ingest that is ~30 commits an hour - and reads cost one file open per file, not
per row. Left alone, ``posts_v1`` reached ~3 400 files and a one-row author
lookup took 650 ms. This job runs :func:`compact_x_datasets` every six hours:
merge small files, rewrite delete-heavy ones, expire snapshots older than a
week and delete the files only they used.

It runs at half past so it never overlaps the hourly ``x_build_app_x_proxy``
rebuild, and skips while a previous compaction is still going. The schedule
starts **RUNNING**; ``x_dataset_compaction`` can also be launched by hand.
"""

from __future__ import annotations

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration

_JOB_NAME = "x_dataset_compaction"
_OP_NAME = "x_dataset_compaction_op"
_SCHEDULE_NAME = "x_dataset_compaction_6h"
_CRON = "30 */6 * * *"
_IN_PROGRESS_STATUSES = [
    dg.DagsterRunStatus.QUEUED,
    dg.DagsterRunStatus.NOT_STARTED,
    dg.DagsterRunStatus.STARTING,
    dg.DagsterRunStatus.STARTED,
]


def _run_compaction() -> dict:
    from naas_abi_marketplace.applications.x import ABIModule
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.maintenance import (
        compact_x_datasets,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
        x_dataset_sync_enabled,
    )

    module = ABIModule.get_instance()
    if not x_dataset_sync_enabled(module):
        logger.info("XDatasetCompactionOrchestration: dataset sync disabled; skipped")
        return {"skipped": "dataset sync disabled"}
    report = compact_x_datasets(module.engine.services.dataset)
    logger.info(f"XDatasetCompactionOrchestration: done — {report}")
    return report


class XDatasetCompactionOrchestration(DagsterOrchestration):
    """Six-hourly compaction of the X DuckLake tables (see module docstring)."""

    @classmethod
    def New(cls) -> XDatasetCompactionOrchestration:
        @dg.op(name=_OP_NAME)
        def compaction_op(_context) -> dict:
            return _run_compaction()

        @dg.job(name=_JOB_NAME, executor_def=dg.in_process_executor)
        def compaction_job():
            compaction_op()

        @dg.schedule(
            name=_SCHEDULE_NAME,
            job=compaction_job,
            cron_schedule=_CRON,
            execution_timezone="UTC",
            default_status=dg.DefaultScheduleStatus.RUNNING,
        )
        def x_dataset_compaction_6h(context: dg.ScheduleEvaluationContext):
            runs = context.instance.get_runs(
                filters=dg.RunsFilter(
                    job_name=_JOB_NAME, statuses=_IN_PROGRESS_STATUSES
                ),
                limit=1,
            )
            if runs:
                return dg.SkipReason("A compaction is still running.")
            return dg.RunRequest(run_key=None)

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[x_dataset_compaction_6h],
                jobs=[compaction_job],
                sensors=[],
            )
        )

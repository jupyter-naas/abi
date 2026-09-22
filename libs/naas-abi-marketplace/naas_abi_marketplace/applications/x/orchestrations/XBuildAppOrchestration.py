"""Scheduled dashboard-rebuild orchestration for the X application.

A single Dagster job (``x_build_app_x_proxy``) that rebuilds the Recent Tweets app from
Dataset Service — no X API calls, no re-ingest, no Fuseki snapshot scans. On every
tick it calls :func:`publish_x_app`, which:

1. reads ``posts_v1`` / ``count_buckets_v1`` via the dataset port, then
2. re-renders the ``x/apps/x_proxy/`` JSON snapshots (globals + count_recent_tweets +
   search_recents_tweets) and the static web export.
3. drains a bounded batch of pending dataset media downloads (formerly the
   ``x_dataset_media_worker_schedule`` every-10-min tick).

Use it to keep the published dashboard fresh on a fixed cadence, independent of
when new tweets/counts land — the ingestion orchestrations already republish on
map, this one guarantees a periodic rebuild even on a quiet ingestion tick.

The schedule starts **RUNNING** by default; stop it from the Dagster UI when
needed. You can also launch ``x_build_app_x_proxy`` manually from the launchpad.
"""

from __future__ import annotations

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration

_JOB_NAME = "x_build_app_x_proxy"
_OP_NAME = "x_build_app_x_proxy_op"
_MEDIA_OP_NAME = "x_dataset_media_worker_op"
_SCHEDULE_NAME = "x_build_app_x_proxy_hourly"
_DAILY_REPORT_JOB_PREFIX = "report_send_counter_uas_daily_"
_IN_PROGRESS_STATUSES = [
    dg.DagsterRunStatus.QUEUED,
    dg.DagsterRunStatus.NOT_STARTED,
    dg.DagsterRunStatus.STARTING,
    dg.DagsterRunStatus.STARTED,
]


def _run_build_cycle() -> dict:
    """Rebuild the X app snapshots from Dataset Service."""
    from naas_abi_marketplace.applications.x import ABIModule
    from naas_abi_marketplace.applications.x.orchestrations.utils import (
        publish_x_app,
    )

    module = ABIModule.get_instance()
    summary: dict = {"app": publish_x_app(module)}
    logger.info(f"XBuildAppOrchestration: done — {summary}")
    return summary


def _default_run_config() -> dict:
    """Launchpad reference — ops in graph execution order (no op config schema)."""
    return {
        "ops": {
            _OP_NAME: {},
            _MEDIA_OP_NAME: {},
        }
    }


def _run_media_batch() -> dict:
    from naas_abi_marketplace.applications.x import ABIModule
    from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_worker import (
        process_pending_media_batch,
    )

    module = ABIModule.get_instance()
    app_cfg = getattr(module.configuration, "app", None)
    dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
    batch = int(getattr(dataset_cfg, "media_batch_size", 4) or 4)
    result = process_pending_media_batch(module, limit=batch)
    logger.info(f"XBuildAppOrchestration: media batch — {result}")
    return result


class XBuildAppOrchestration(DagsterOrchestration):
    """Scheduled job that rebuilds the X app dashboard from Dataset Service.

    Launchpad: run ``x_build_app_x_proxy`` to re-render snapshots + web export on demand.
    Requires ``app.dataset.read_enabled: true`` and Dataset Service on the engine.
    """

    @classmethod
    def New(cls) -> XBuildAppOrchestration:
        @dg.op(name=_OP_NAME)
        def build_op(_context) -> dict:
            return _run_build_cycle()

        @dg.op(name=_MEDIA_OP_NAME, tags={"x_dataset_media": "1"})
        def media_worker_op(_build_summary: dict) -> dict:
            return _run_media_batch()

        @dg.job(
            name=_JOB_NAME,
            executor_def=dg.in_process_executor,
            config=_default_run_config(),
        )
        def build_job():
            media_worker_op(build_op())

        @dg.schedule(
            name=_SCHEDULE_NAME,
            job=build_job,
            cron_schedule="0 * * * *",
            execution_timezone="UTC",
            default_status=dg.DefaultScheduleStatus.RUNNING,
        )
        def x_build_app_x_proxy_hourly(context: dg.ScheduleEvaluationContext):
            runs = context.instance.get_runs(
                filters=dg.RunsFilter(statuses=_IN_PROGRESS_STATUSES),
                limit=100,
            )
            if any(
                (run.job_name or "").startswith(_DAILY_REPORT_JOB_PREFIX)
                for run in runs
            ):
                return dg.SkipReason(
                    "A daily Counter-UAS report is in progress; "
                    "deferring X Proxy rebuild."
                )
            return dg.RunRequest(run_key=None)

        schedule = x_build_app_x_proxy_hourly

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[schedule],
                jobs=[build_job],
                sensors=[],
            )
        )

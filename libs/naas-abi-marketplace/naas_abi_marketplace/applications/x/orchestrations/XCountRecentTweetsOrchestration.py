"""Hourly count-following orchestration for the X application.

One Dagster job on an hourly schedule that, for every configured
``count_recent_tweets_workflow`` query:

1. runs :class:`XCountRecentTweetsWorkflow` to fetch the newly completed clock
   hour(s) of tweet counts and persist a JSON envelope (7-day backfill on the
   first run, last-full-hour only afterwards),
2. maps each saved envelope into the ``x_recent_posts_count`` graph via
   :class:`XCountRecentTweetsPipeline`, then
3. republishes the X app dashboard + JSON snapshots to
   ``x/apps/x/`` from the graph (:class:`XAppHubBuilder`).

The schedule is created RUNNING when at least one configured query is enabled,
otherwise STOPPED; either way you can toggle it from the Dagster UI. Launch the
job manually from the launchpad to run all configured queries on demand.
"""

from __future__ import annotations

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import ABIModule

_JOB_NAME = "x_count_recent_tweets"
_OP_NAME = "x_count_recent_tweets_op"
_SCHEDULE_NAME = "x_count_recent_tweets_hourly"


def _enabled_queries(module) -> list:
    return [
        entry
        for entry in (
            getattr(module.configuration, "count_recent_tweets_workflow", []) or []
        )
        if getattr(entry, "enabled", False)
    ]


def _run_count_cycle() -> dict:
    """Fetch → map → publish for every enabled count-following query."""
    from naas_abi_marketplace.applications.x.orchestrations.utils import (
        publish_x_app,
        run_count_for_query,
    )

    module = ABIModule.get_instance()
    entries = _enabled_queries(module)
    if not entries:
        logger.info(
            "XCountRecentTweetsOrchestration: no enabled queries; nothing to do"
        )
        return {"queries": 0, "buckets": 0, "mapped": 0}

    total_buckets = 0
    mapped = 0
    for entry in entries:
        result = run_count_for_query(module, entry.query)
        total_buckets += result["buckets"]
        mapped += result["mapped"]

    # Republish the dashboard + JSON snapshots from the (now updated) graph, for
    # every followed query (enabled count entries + search filters that opted in).
    publish = publish_x_app(module)
    summary = {
        "queries": len(entries),
        "buckets": total_buckets,
        "mapped": mapped,
        "app": publish,
    }
    logger.info(f"XCountRecentTweetsOrchestration: done — {summary}")
    return summary


class XCountRecentTweetsOrchestration(DagsterOrchestration):
    """Hourly job that follows X post counts and republishes the dashboard.

    Launchpad: run ``x_count_recent_tweets`` to process every enabled
    ``count_recent_tweets_workflow`` query on demand.
    """

    @classmethod
    def New(cls) -> XCountRecentTweetsOrchestration:
        module = ABIModule.get_instance()
        has_enabled = bool(_enabled_queries(module))

        @dg.op(name=_OP_NAME)
        def count_op(context) -> dict:
            return _run_count_cycle()

        # In-process executor: share the code-server's warm engine instead of
        # forking a subprocess that re-bootstraps and races oxigraph / nexus.db.
        @dg.job(name=_JOB_NAME, executor_def=dg.in_process_executor)
        def count_job():
            count_op()

        schedule = dg.ScheduleDefinition(
            name=_SCHEDULE_NAME,
            job=count_job,
            cron_schedule="0 * * * *",  # top of every hour
            execution_timezone="UTC",
            default_status=(
                dg.DefaultScheduleStatus.RUNNING
                if has_enabled
                else dg.DefaultScheduleStatus.STOPPED
            ),
        )

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[schedule],
                jobs=[count_job],
                sensors=[],
            )
        )

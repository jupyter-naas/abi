"""Scheduled dashboard-rebuild orchestration for the X application.

A single Dagster job (``x_build_app``) that rebuilds the Recent Tweets app from
the current graph — no X API calls, no re-ingest, no re-map. On every tick it
calls :func:`publish_x_app`, which:

1. reads the ``x_recent_posts_count`` / tweet graphs from the triple store, then
2. re-renders the ``x/apps/x/`` JSON snapshots (globals + count_recent_tweets +
   search_recents_tweets) and the static web export from that graph state.

Use it to keep the published dashboard fresh on a fixed cadence, independent of
when new tweets/counts land — the ingestion orchestrations already republish on
map, this one guarantees a periodic rebuild even on a quiet ingestion tick.

The schedule is created RUNNING when module ``app.publish`` is true (the
default) and STOPPED otherwise; either way you can toggle it from the Dagster UI
and launch ``x_build_app`` manually from the launchpad to rebuild on demand.
"""

from __future__ import annotations

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import ABIModule

_JOB_NAME = "x_build_app"
_OP_NAME = "x_build_app_op"
_SCHEDULE_NAME = "x_build_app_hourly"


def _run_build_cycle() -> dict:
    """Populate from the triple store and rebuild the X app front."""
    from naas_abi_marketplace.applications.x.orchestrations.utils import publish_x_app

    module = ABIModule.get_instance()
    publish = publish_x_app(module)
    summary = {"app": publish}
    logger.info(f"XBuildAppOrchestration: done — {summary}")
    return summary


class XBuildAppOrchestration(DagsterOrchestration):
    """Scheduled job that rebuilds the X app dashboard from the graph.

    Launchpad: run ``x_build_app`` to re-render the ``x/apps/x/`` snapshots +
    web export from the current triple-store state on demand.
    """

    @classmethod
    def New(cls) -> XBuildAppOrchestration:
        from naas_abi_marketplace.applications.x.orchestrations.utils import (
            x_app_publish_enabled,
        )

        module = ABIModule.get_instance()
        publish_enabled = x_app_publish_enabled(module)

        @dg.op(name=_OP_NAME)
        def build_op(context) -> dict:
            return _run_build_cycle()

        # In-process executor: share the code-server's warm engine instead of
        # forking a subprocess that re-bootstraps and races oxigraph / nexus.db.
        @dg.job(name=_JOB_NAME, executor_def=dg.in_process_executor)
        def build_job():
            build_op()

        schedule = dg.ScheduleDefinition(
            name=_SCHEDULE_NAME,
            job=build_job,
            cron_schedule="0 * * * *",  # top of every hour
            execution_timezone="UTC",
            default_status=(
                dg.DefaultScheduleStatus.RUNNING
                if publish_enabled
                else dg.DefaultScheduleStatus.STOPPED
            ),
        )

        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[schedule],
                jobs=[build_job],
                sensors=[],
            )
        )

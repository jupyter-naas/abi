"""Scheduled dashboard-rebuild orchestration for the X application.

A single Dagster job (``x_build_app``) that rebuilds the Recent Tweets app from
the current graph — no X API calls, no re-ingest, no re-map. On every tick it
calls :func:`publish_x_app`, which:

1. reads the ``x_recent_posts_count`` / tweet graphs from the triple store, then
2. re-renders the ``x/apps/x_proxy/`` JSON snapshots (globals + count_recent_tweets +
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


_BUILD_APP_OP_CONFIG_SCHEMA = {
    "full_users": dg.Field(
        bool,
        is_required=False,
        default_value=False,
        description=(
            "Rebuild every Users shard instead of only the ones whose authors "
            "changed. The incremental default skips querying posts for "
            "unchanged shards; use this to pick up profile edits that arrived "
            "without a new post."
        ),
    ),
    "rebuild_projection": dg.Field(
        bool,
        is_required=False,
        default_value=False,
        description=(
            "Re-project the Parquet cache from the whole envelope archive "
            "instead of only the envelopes past the watermark. Use after a "
            "schema change, a suspected gap, or to compact month partitions "
            "that were duplicated when a missing watermark appended a full "
            "archive dump. Costs a full archive read, so it is not the "
            "scheduled behaviour."
        ),
    ),
}


def _run_build_cycle(
    *, full_users: bool = False, rebuild_projection: bool = False
) -> dict:
    """Populate from the triple store and rebuild the X app front."""
    from naas_abi_marketplace.applications.x.orchestrations.utils import (
        publish_x_app,
        refresh_x_cache,
    )

    module = ABIModule.get_instance()
    summary: dict = {}
    if rebuild_projection:
        # Done up front so the publish below reads the rebuilt projection;
        # publish_x_app's own incremental refresh then has nothing left to do.
        summary["projection_rebuild"] = refresh_x_cache(module, full=True)
    summary["app"] = publish_x_app(module, full_users=full_users)
    logger.info(f"XBuildAppOrchestration: done — {summary}")
    return summary


class XBuildAppOrchestration(DagsterOrchestration):
    """Scheduled job that rebuilds the X app dashboard from the graph.

    Launchpad: run ``x_build_app`` to re-render the ``x/apps/x_proxy/`` snapshots +
    web export from the current triple-store state on demand::

        ops:
          x_build_app_op:
            config:
              full_users: true
              rebuild_projection: true

    ``rebuild_projection`` rewrites every monthly Parquet part from the envelope
    archive (one file per month). Use it after an OOM or a missing Redis
    watermark that appended a second copy of history — the hourly tick must
    stay incremental.
    """

    @classmethod
    def New(cls) -> XBuildAppOrchestration:
        from naas_abi_marketplace.applications.x.orchestrations.utils import (
            x_app_publish_enabled,
        )

        module = ABIModule.get_instance()
        publish_enabled = x_app_publish_enabled(module)

        @dg.op(name=_OP_NAME, config_schema=_BUILD_APP_OP_CONFIG_SCHEMA)
        def build_op(context) -> dict:
            config = context.op_config or {}
            return _run_build_cycle(
                full_users=bool(config.get("full_users", False)),
                rebuild_projection=bool(config.get("rebuild_projection", False)),
            )

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

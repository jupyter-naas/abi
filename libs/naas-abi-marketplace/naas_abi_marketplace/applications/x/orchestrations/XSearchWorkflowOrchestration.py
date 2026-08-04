"""Search-workflow orchestration for the X application.

One job per ``search_recent_tweets_workflow`` entry, plus the single trigger
that runs it — a **sensor** when the entry sets ``interval_seconds`` (wakes on
that cadence of elapsed time), or a **schedule** when it sets ``cron`` (fires at
those wall-clock times, UTC). Setting both is rejected at config load. Either
trigger skips the tick when a run for that filter is already in flight, and
otherwise starts a job that drives :class:`XSearchRecentTweetsWorkflow`
(``since_id`` read from that query's cursor in object storage).

This orchestration is **fetch-and-save only**: the workflow calls the X v2
``search_recent_tweets`` endpoint and persists each ``{query, options, results,
…}`` envelope to object storage. It does **not** map anything into the graph,
and it does **not** republish the dashboard unless the filter sets
``app_publish: true`` — ``x_build_app`` owns that on its own schedule.
Saving an envelope publishes an ``ObjectPut`` event, which
:class:`XSearchRecentTweetsEventOrchestration` consumes to map the file into the
graph via :class:`XSearchRecentTweetsPipeline`. Keep that event sensor enabled
for tweets to reach the triple store.

All triggers are **disabled by default** (``DefaultSensorStatus.STOPPED`` /
``DefaultScheduleStatus.STOPPED``); enable them explicitly from the Dagster UI.

Launch from the Dagster launchpad to override per-run workflow parameters.
Omitted fields use the matching ``search_recent_tweets_workflow`` entry from the
ABI config.

Launchpad example (for a filter named ``ai_llms``)::

    ops:
      x_search_workflow_op_ai_llms:
        config:
          max_pages: 2
          daily_max_usd: 5.0
"""

import dagster as dg
from naas_abi_core import logger
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import (
    ABIModule,
    XTweetSearchWorkflowConfiguration,
)
from naas_abi_marketplace.applications.x.orchestrations.utils import (
    has_in_progress_run,
    run_search_workflow_for_filter,
    safe_name,
)

_SEARCH_WORKFLOW_OP_CONFIG_SCHEMA = {
    "query": dg.Field(
        str,
        is_required=False,
        description="X v2 search query (ABI filter config default).",
    ),
    "max_results": dg.Field(
        int,
        is_required=False,
        description="Page size forwarded to search_recent_tweets.",
    ),
    "max_pages": dg.Field(
        int,
        is_required=False,
        description="Maximum pages to fetch per run (null = no limit).",
    ),
    "save_every_pages": dg.Field(
        int,
        is_required=False,
        description="Flush a new envelope every N pages during pagination.",
    ),
    "save_every_tweets": dg.Field(
        int,
        is_required=False,
        description="Flush a new envelope every N tweets during pagination.",
    ),
    "sort_order": dg.Field(
        str,
        is_required=False,
        description="Result order: recency or relevancy.",
    ),
    "cost_per_tweet_usd": dg.Field(
        float,
        is_required=False,
        description="USD billed per tweet returned by search_recent_tweets.",
    ),
    "daily_max_tweets": dg.Field(
        int,
        is_required=False,
        description="Max tweets this filter may retrieve per UTC day.",
    ),
    "daily_max_usd": dg.Field(
        float,
        is_required=False,
        description="Max USD this filter may spend per UTC day.",
    ),
    "monthly_max_tweets": dg.Field(
        int,
        is_required=False,
        description="Max tweets this filter may retrieve per calendar month.",
    ),
    "monthly_max_usd": dg.Field(
        float,
        is_required=False,
        description="Max USD this filter may spend per calendar month.",
    ),
    "count_recent_tweets": dg.Field(
        bool,
        is_required=False,
        description=(
            "Also fetch the recent-post count for this query on the same tick."
        ),
    ),
    "app_publish": dg.Field(
        bool,
        is_required=False,
        description=(
            "Republish the x/apps/x/ snapshots after this run. Off by default — "
            "a publish re-reads the whole graph and the hourly x_build_app "
            "schedule already does it."
        ),
    ),
}


def _trigger_description(config: XTweetSearchWorkflowConfiguration) -> str:
    """Human-readable summary shown on the filter's sensor / schedule."""
    cadence = (
        f"on cron '{config.cron}' (UTC)"
        if config.cron
        else f"every {config.interval_seconds}s"
    )
    return (
        f"Poll X v2 search_recent_tweets for filter '{config.name}' "
        f"(query={config.query!r}) {cadence} via XSearchRecentTweetsWorkflow "
        f"and save any tweets newer than the last persisted newest_id. Graph "
        f"mapping is handled separately by the ObjectPut event sensor."
    )


def _build_search_workflow_definitions(
    config: XTweetSearchWorkflowConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition | None, dg.ScheduleDefinition | None]:
    """Build the job that fetches tweets matching *config* via
    :class:`XSearchRecentTweetsWorkflow`, plus the one trigger that runs it.

    Job-per-filter so Dagster sensors/schedules (which bind to a single job)
    throttle independently. The job is a single op that drives the *workflow*
    (``since_id`` read from that query's cursor in object storage)
    to fetch and save the envelopes — no graph mapping here; the saved
    envelopes' ObjectPut events drive XSearchRecentTweetsEventOrchestration to
    map them.

    Exactly one of the returned trigger slots is populated: a sensor for an
    ``interval_seconds`` filter, a schedule for a ``cron`` one (the config model
    rejects entries that set both).
    """

    safe = safe_name(config.name)
    job_name = f"x_search_workflow_{safe}"
    op_name = f"x_search_workflow_op_{safe}"
    sensor_name = f"x_search_workflow_sensor_{safe}"
    schedule_name = f"x_search_workflow_schedule_{safe}"
    description = _trigger_description(config)

    @dg.op(name=op_name, config_schema=_SEARCH_WORKFLOW_OP_CONFIG_SCHEMA)
    def search_workflow_op(context) -> list[str]:
        return run_search_workflow_for_filter(config, context.op_config or {})

    # In-process executor: share the code-server's warm engine instead of
    # forking a subprocess that has to re-bootstrap and race the api on
    # oxigraph / nexus.db.
    @dg.job(name=job_name, executor_def=dg.in_process_executor)
    def search_workflow_job():
        search_workflow_op()

    if config.cron:

        @dg.schedule(
            name=schedule_name,
            description=description,
            job=search_workflow_job,
            cron_schedule=config.cron,
            execution_timezone="UTC",
            default_status=dg.DefaultScheduleStatus.STOPPED,
        )
        def search_workflow_schedule(context: dg.ScheduleEvaluationContext):
            # Same guard as the sensor path: a slow run must not stack up with
            # the next tick — the skipped tick is picked up by the following
            # one (since_id makes the fetch incremental either way).
            if has_in_progress_run(context, job_name):
                return dg.SkipReason(f"Job '{job_name}' is already running.")
            return [dg.RunRequest(run_key=None)]

        return search_workflow_job, None, search_workflow_schedule

    @dg.sensor(
        name=sensor_name,
        description=description,
        job=search_workflow_job,
        minimum_interval_seconds=config.interval_seconds,
        default_status=dg.DefaultSensorStatus.STOPPED,
    )
    def search_workflow_sensor(context: dg.SensorEvaluationContext):
        if has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")
        return [dg.RunRequest(run_key=None)]

    return search_workflow_job, search_workflow_sensor, None


class XSearchWorkflowOrchestration(DagsterOrchestration):
    """One job per configured ``search_recent_tweets_workflow`` filter — driven
    by a sensor (``interval_seconds``) or a schedule (``cron``) — each running
    :class:`XSearchRecentTweetsWorkflow` to fetch and save tweet envelopes (no
    graph mapping — that is event-driven via
    :class:`XSearchRecentTweetsEventOrchestration`). Triggers disabled by default.

    Launchpad example (replace ``ai_llms`` with your filter name)::

        ops:
          x_search_workflow_op_ai_llms:
            config:
              query: "(openai OR anthropic) lang:en -is:retweet"
              max_results: 50
    """

    @classmethod
    def New(cls) -> "XSearchWorkflowOrchestration":
        module = ABIModule.get_instance()

        jobs: list[dg.JobDefinition] = []
        sensors: list[dg.SensorDefinition] = []
        schedules: list[dg.ScheduleDefinition] = []

        seen_workflow_names: set[str] = set()
        for workflow_config in module.configuration.search_recent_tweets_workflow:
            if workflow_config.name in seen_workflow_names:
                logger.warning(
                    f"XSearchWorkflowOrchestration: duplicate "
                    f"search_recent_tweets_workflow name {workflow_config.name!r}; "
                    f"skipping the duplicate"
                )
                continue
            seen_workflow_names.add(workflow_config.name)
            job, sensor, schedule = _build_search_workflow_definitions(workflow_config)
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

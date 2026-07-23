"""Search-workflow orchestration for the X application.

One (job, sensor) pair per ``search_recent_tweets_workflow`` entry. The sensor
wakes every ``interval_seconds`` and, unless a run for that filter is already in
flight, triggers a job that drives :class:`XSearchRecentTweetsWorkflow`
(``since_id`` recovered from the persisted JSON envelopes in object storage).

This orchestration is **fetch-and-save only**: the workflow calls the X v2
``search_recent_tweets`` endpoint and persists each ``{query, options, results,
…}`` envelope to object storage. It does **not** map anything into the graph.
Saving an envelope publishes an ``ObjectPut`` event, which
:class:`XSearchRecentTweetsEventOrchestration` consumes to map the file into the
graph via :class:`XSearchRecentTweetsPipeline`. Keep that event sensor enabled
for tweets to reach the triple store.

All sensors are **disabled by default** (``DefaultSensorStatus.STOPPED``); enable
them explicitly from the Dagster UI.

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
    launchpad_override,
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
}


def _run_search_workflow(
    filter_config: XTweetSearchWorkflowConfiguration,
    op_cfg: dict | None = None,
) -> list[str]:
    """Fetch tweets for *filter_config* and persist the JSON envelopes.

    Returns the object-storage paths of the envelopes the workflow wrote. The
    graph mapping is **not** done here — each saved envelope's ObjectPut event
    drives XSearchRecentTweetsEventOrchestration to map it.
    """
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
        XSearchRecentTweetsWorkflowConfiguration,
        XSearchRecentTweetsWorkflowParameters,
    )

    op_cfg = op_cfg or {}
    module = ABIModule.get_instance()
    query = launchpad_override(op_cfg, "query", filter_config.query)
    max_results = launchpad_override(op_cfg, "max_results", filter_config.max_results)
    max_pages = launchpad_override(op_cfg, "max_pages", filter_config.max_pages)
    sort_order = launchpad_override(op_cfg, "sort_order", filter_config.sort_order)
    save_every_pages = launchpad_override(
        op_cfg, "save_every_pages", filter_config.save_every_pages
    )
    save_every_tweets = launchpad_override(
        op_cfg, "save_every_tweets", filter_config.save_every_tweets
    )

    options: dict = {
        "max_results": max_results,
        "max_pages": max_pages,
        "sort_order": sort_order,
        "save_every_pages": save_every_pages,
        "save_every_tweets": save_every_tweets,
    }

    logger.info(
        f"XSearchWorkflowOrchestration[{filter_config.name}]: running "
        f"XSearchRecentTweetsWorkflow(query={query!r}) — fetch + save only "
        f"(save_every_pages={save_every_pages}, "
        f"save_every_tweets={save_every_tweets})"
    )

    # XIntegration and the workflow both default datastore_path to the
    # module's configuration, so the envelopes the integration writes are
    # the same ones the workflow scans to recover since_id.
    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )
    workflow = XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=module.engine.services.object_storage,
            budget_key=filter_config.name,
            save_every_pages=save_every_pages,
            save_every_tweets=save_every_tweets,
            cost_per_tweet_usd=launchpad_override(
                op_cfg, "cost_per_tweet_usd", filter_config.cost_per_tweet_usd
            ),
            daily_max_tweets=launchpad_override(
                op_cfg, "daily_max_tweets", filter_config.daily_max_tweets
            ),
            daily_max_usd=launchpad_override(
                op_cfg, "daily_max_usd", filter_config.daily_max_usd
            ),
            monthly_max_tweets=launchpad_override(
                op_cfg, "monthly_max_tweets", filter_config.monthly_max_tweets
            ),
            monthly_max_usd=launchpad_override(
                op_cfg, "monthly_max_usd", filter_config.monthly_max_usd
            ),
        )
    )
    output = workflow.run(
        XSearchRecentTweetsWorkflowParameters(
            queries=[query],
            options=options,
        )
    )

    file_paths: list[str] = []
    for item in output.get("results", []):
        paths = item.get("file_paths") or []
        if paths:
            file_paths.extend(paths)
        elif item.get("file_path"):
            file_paths.append(item["file_path"])
    logger.info(
        f"XSearchWorkflowOrchestration[{filter_config.name}]: saved "
        f"{len(file_paths)} envelope(s); the ObjectPut sensor will map them."
    )
    return file_paths


def _build_search_workflow_job_sensor(
    config: XTweetSearchWorkflowConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    """Build the (job, sensor) pair that fetches tweets matching *config* via
    :class:`XSearchRecentTweetsWorkflow`.

    Job-per-filter so Dagster sensors (which bind to a single job) throttle
    independently. The job is a single op that drives the *workflow* (``since_id``
    recovered from the persisted JSON envelopes in object storage) to fetch and
    save the envelopes — no graph mapping here; the saved envelopes' ObjectPut
    events drive XSearchRecentTweetsEventOrchestration to map them.
    """

    safe = safe_name(config.name)
    job_name = f"x_search_workflow_{safe}"
    op_name = f"x_search_workflow_op_{safe}"
    sensor_name = f"x_search_workflow_sensor_{safe}"

    @dg.op(name=op_name, config_schema=_SEARCH_WORKFLOW_OP_CONFIG_SCHEMA)
    def search_workflow_op(context) -> list[str]:
        return _run_search_workflow(config, context.op_config or {})

    # In-process executor: share the code-server's warm engine instead of
    # forking a subprocess that has to re-bootstrap and race the api on
    # oxigraph / nexus.db.
    @dg.job(name=job_name, executor_def=dg.in_process_executor)
    def search_workflow_job():
        search_workflow_op()

    @dg.sensor(
        name=sensor_name,
        description=(
            f"Poll X v2 search_recent_tweets for filter '{config.name}' "
            f"(query={config.query!r}) every {config.interval_seconds}s via "
            f"XSearchRecentTweetsWorkflow and save any tweets newer than the "
            f"last persisted newest_id. Graph mapping is handled separately by "
            f"the ObjectPut event sensor."
        ),
        job=search_workflow_job,
        minimum_interval_seconds=config.interval_seconds,
        default_status=dg.DefaultSensorStatus.STOPPED,
    )
    def search_workflow_sensor(context: dg.SensorEvaluationContext):
        if has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")
        return [dg.RunRequest(run_key=None)]

    return search_workflow_job, search_workflow_sensor


class XSearchWorkflowOrchestration(DagsterOrchestration):
    """One (job, sensor) pair per configured ``search_recent_tweets_workflow``
    filter, each driving :class:`XSearchRecentTweetsWorkflow` to fetch and save
    tweet envelopes (no graph mapping — that is event-driven via
    :class:`XSearchRecentTweetsEventOrchestration`). Sensors disabled by default.

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
            job, sensor = _build_search_workflow_job_sensor(workflow_config)
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

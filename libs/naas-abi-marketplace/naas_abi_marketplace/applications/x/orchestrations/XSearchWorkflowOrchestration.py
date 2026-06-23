"""Search-workflow orchestration for the X application.

One (job, sensor) pair per ``search_recent_tweets_workflow`` entry. The sensor
wakes every ``interval_seconds`` and, unless a run for that filter is already in
flight, triggers a job that drives :class:`XSearchRecentTweetsWorkflow`
(``since_id`` recovered from the persisted JSON envelopes in object storage),
then feeds each persisted envelope's ``file_path`` to
:class:`XSearchRecentTweetsPipeline` to map it into the graph.

All sensors are **disabled by default** (``DefaultSensorStatus.STOPPED``); enable
them explicitly from the Dagster UI.
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
    run_search_pipeline_for_file,
    safe_name,
)


def _build_search_workflow_job_sensor(
    config: XTweetSearchWorkflowConfiguration,
) -> tuple[dg.JobDefinition, dg.SensorDefinition]:
    """Build the (job, sensor) pair that ingests tweets matching *config* via
    :class:`XSearchRecentTweetsWorkflow`.

    Job-per-filter so Dagster sensors (which bind to a single job) throttle
    independently. The job is two chained ops: the first drives the *workflow*
    (``since_id`` recovered from the persisted JSON envelopes in object storage)
    and returns each persisted envelope's ``file_path``; the second feeds those
    paths to :class:`XSearchRecentTweetsPipeline` in ``file_path`` mode, which
    maps the full SearchQuery / SearchResultSet / SearchRecentTweets structure
    into the graph from the same files.
    """

    safe = safe_name(config.name)
    job_name = f"x_search_workflow_{safe}"
    op_name = f"x_search_workflow_op_{safe}"
    pipeline_op_name = f"x_search_workflow_pipeline_op_{safe}"
    sensor_name = f"x_search_workflow_sensor_{safe}"

    @dg.op(name=op_name)
    def search_workflow_op() -> list[str]:
        from naas_abi_marketplace.applications.x.integrations.XIntegration import (
            XIntegration,
            XIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
            XSearchRecentTweetsWorkflow,
            XSearchRecentTweetsWorkflowConfiguration,
            XSearchRecentTweetsWorkflowParameters,
        )

        module = ABIModule.get_instance()

        # Request the rich fields the rest of the pipeline maps into the graph
        # (XUser via author_id, TweetPublicMetrics via public_metrics,
        # TweetLanguage via lang, tweet_created_at). Without these the X v2
        # search endpoint only returns {id, text} and the agent's engagement /
        # language / author queries all come up empty.
        options: dict = {
            "max_results": config.max_results,
            "max_pages": config.max_pages,
            "sort_order": config.sort_order,
        }

        logger.info(
            f"XSearchWorkflowOrchestration[{config.name}]: running "
            f"XSearchRecentTweetsWorkflow(query={config.query!r}, "
            f"persist={config.persist})"
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
            )
        )
        output = workflow.run(
            XSearchRecentTweetsWorkflowParameters(
                queries=[config.query],
                options=options,
                persist=config.persist,
            )
        )

        # Hand each persisted envelope's path to the downstream pipeline op so
        # the full SearchQuery / SearchRecentTweets structure is mapped from the
        # same file the workflow just wrote.
        return [
            item["file_path"]
            for item in output.get("results", [])
            if item.get("file_path")
        ]

    @dg.op(name=pipeline_op_name)
    def search_workflow_pipeline_op(file_paths: list[str]) -> None:
        for file_path in file_paths:
            run_search_pipeline_for_file(file_path)

    # In-process executor: share the code-server's warm engine instead of
    # forking a subprocess that has to re-bootstrap and race the api on
    # oxigraph / nexus.db.
    @dg.graph(name=job_name)
    def search_workflow_graph():
        # File-path output of the workflow op triggers the pipeline op.
        search_workflow_pipeline_op(search_workflow_op())

    job = search_workflow_graph.to_job(
        name=job_name, executor_def=dg.in_process_executor
    )

    @dg.sensor(
        name=sensor_name,
        description=(
            f"Poll X v2 search_recent_tweets for filter '{config.name}' "
            f"(query={config.query!r}) every {config.interval_seconds}s via "
            f"XSearchRecentTweetsWorkflow and ingest any tweets newer than the "
            f"last persisted newest_id."
        ),
        job=job,
        minimum_interval_seconds=config.interval_seconds,
        default_status=dg.DefaultSensorStatus.STOPPED,
    )
    def search_workflow_sensor(context: dg.SensorEvaluationContext):
        if has_in_progress_run(context, job_name):
            return dg.SkipReason(f"Job '{job_name}' is already running.")
        return [dg.RunRequest(run_key=None)]

    return job, search_workflow_sensor


class XSearchWorkflowOrchestration(DagsterOrchestration):
    """One (job, sensor) pair per configured ``search_recent_tweets_workflow``
    filter, each driving :class:`XSearchRecentTweetsWorkflow` then
    :class:`XSearchRecentTweetsPipeline`. Sensors disabled by default.
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

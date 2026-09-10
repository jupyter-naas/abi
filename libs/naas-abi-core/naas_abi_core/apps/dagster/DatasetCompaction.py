"""Dagster entry point for dataset file maintenance."""

import dagster as dg

from naas_abi_core.services.dataset.DatasetService import DatasetService


@dg.op(
    required_resource_keys={"dataset_compaction_service"},
    config_schema={
        "namespace": dg.Field(dg.Noneable(str), default_value=None),
        "name": dg.Field(dg.Noneable(str), default_value=None),
        "inline_warning_threshold": dg.Field(int, default_value=100_000),
    },
)
def compact_datasets(context: dg.OpExecutionContext) -> None:
    service: DatasetService = context.resources.dataset_compaction_service
    namespace = context.op_config["namespace"]
    name = context.op_config["name"]
    if name is not None:
        datasets = [service.describe(name, namespace=namespace or "default")]
    else:
        datasets = service.list(namespace=namespace)
    for dataset in datasets:
        service.check_catalog_pressure(
            dataset.name,
            namespace=dataset.namespace,
            threshold_records=context.op_config["inline_warning_threshold"],
        )
        flushed = service.flush(dataset.name, namespace=dataset.namespace)
        context.log.info(
            "Flushed %s.%s: %s", dataset.namespace, dataset.name, flushed.rows
        )
        result = service.compact(dataset.name, namespace=dataset.namespace)
        context.log.info(
            "Compacted %s.%s: %s", dataset.namespace, dataset.name, result.rows
        )
    context.add_output_metadata({"datasets_processed": len(datasets)})


@dg.job(
    description="Flush inline data, then merge small files within partitions; preserve snapshots."
)
def dataset_compaction_job() -> None:
    compact_datasets()


@dg.op(
    required_resource_keys={"dataset_compaction_service"},
    config_schema={"inline_warning_threshold": dg.Field(int, default_value=100_000)},
)
def check_dataset_catalogs(context: dg.OpExecutionContext) -> None:
    service: DatasetService = context.resources.dataset_compaction_service
    for dataset in service.list():
        count = service.check_catalog_pressure(
            dataset.name,
            namespace=dataset.namespace,
            threshold_records=context.op_config["inline_warning_threshold"],
        )
        context.log.info(
            "%s.%s: %s unflushed catalog records",
            dataset.namespace,
            dataset.name,
            count,
        )


@dg.job(description="Report accumulated inline records without interrupting ingestion.")
def dataset_catalog_monitor_job() -> None:
    check_dataset_catalogs()


def dataset_compaction_definitions(service: DatasetService) -> dg.Definitions:
    return dg.Definitions(
        jobs=[dataset_compaction_job, dataset_catalog_monitor_job],
        resources={
            "dataset_compaction_service": dg.ResourceDefinition.hardcoded_resource(
                service
            )
        },
        schedules=[
            dg.ScheduleDefinition(
                name="dataset_compaction_daily",
                job=dataset_compaction_job,
                cron_schedule="0 2 * * *",
                execution_timezone="UTC",
                default_status=dg.DefaultScheduleStatus.RUNNING,
            ),
            dg.ScheduleDefinition(
                name="dataset_catalog_monitor_hourly",
                job=dataset_catalog_monitor_job,
                cron_schedule="0 * * * *",
                execution_timezone="UTC",
                default_status=dg.DefaultScheduleStatus.RUNNING,
            ),
        ],
    )

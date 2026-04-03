# Dagster

Dagster is ABI's orchestration layer for scheduled jobs, data pipelines, and asset materialization.

---

## Starting Dagster

```bash
make dagster-dev           # Development server with live reload
make dagster-up            # Background service
make dagster-ui            # Open web UI in browser (port 3001)
```

---

## What Dagster does in ABI

Dagster orchestrates ABI pipelines as **assets** - materialized data artifacts with lineage tracking, scheduling, and failure recovery. Use it when you want to:

- Run data ingestion pipelines on a schedule (e.g. sync LinkedIn data every hour).
- Track which data assets are stale and need re-computation.
- Retry failed pipeline runs automatically.
- Monitor pipeline health in a visual UI.

---

## Defining a Dagster asset from a pipeline

```python
# orchestrations/MyOrchestration.py
from dagster import asset, AssetExecutionContext
from naas_abi.modules.custom.my_module.pipelines.MyPipeline import (
    MyPipeline, MyPipelineConfiguration, MyPipelineParameters,
)

@asset(
    name="my_service_items",
    description="Items from MyService, ingested into the knowledge graph",
    group_name="my_module",
)
def my_service_items_asset(context: AssetExecutionContext) -> None:
    pipeline = MyPipeline(
        MyPipelineConfiguration(
            integration_config=...,
            triple_store_service=...,
        )
    )
    result = pipeline.run(MyPipelineParameters())
    context.log.info(f"Ingested {result['triples_added']} triples")
```

---

## Scheduling assets

```python
from dagster import ScheduleDefinition, define_asset_job

hourly_sync_job = define_asset_job(
    name="hourly_myservice_sync",
    selection=["my_service_items"],
)

hourly_schedule = ScheduleDefinition(
    job=hourly_sync_job,
    cron_schedule="0 * * * *",   # Every hour
)
```

---

## Service management

```bash
make dagster-status         # Check asset materialization status
make dagster-materialize    # Trigger all assets immediately
make dagster-down           # Stop Dagster service
```

# Dagster (legacy)

:::warning Legacy
Dagster is a **legacy, optional extra** since ABI 3.0 and will be removed in the next major. New projects run on NATS, where [module jobs](/user-guide/build/modules/module-jobs) replace it: each module declares its jobs and runs them in its own process, and JetStream schedules them. Move orchestrations to module jobs before you turn NATS on: [Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3). The rest of the opt-in setup is on [Legacy mode: without NATS](/user-guide/get-started/legacy-mode).
:::

Dagster schedules jobs, data pipelines, and asset materialization for projects **without NATS** (no `nats:` block in the config, or `abi new project --without-nats`).

---

## Installing the legacy extra

`naas-abi-core` no longer installs Dagster, and `naas-abi-core[all]` does not include it. A project without NATS needs the `dagster` extra (and `rabbitmq` for a RabbitMQ bus):

```bash
uv add 'naas-abi-core[all,dagster,rabbitmq]'
```

`abi new project --without-nats` and `abi deploy local` (for a project without a `nats:` block) add it for you. Without it, `DagsterOrchestration.New()`, the RabbitMQ bus adapter and the Dagster app raise `MissingLegacyExtra` (a `ModuleNotFoundError` that prints the `uv add` command), the engine leaves out modules' Dagster orchestrations (one INFO line per module), and `abi dev up` leaves Dagster out with a notice. The extra keeps SQLAlchemy below 2.1, which breaks Dagster 1.13's PostgreSQL storage.

In NATS mode one engine serves the kernel services, so Dagster, a second engine, cannot run next to the API (`EngineAlreadyServing`): the NATS stack has no Dagster service, and `abi dev up` leaves it out.

---

## Starting Dagster

In a project without NATS, `abi dev up` starts Dagster natively, and the classic Docker Compose stack (`abi deploy local`) runs it as the `dagster` service. In the ABI repository, Dagster sits behind the `legacy` Compose profile; its Makefile targets run `docker compose --profile legacy ...`:

```bash
make dagster-dev           # Foreground
make dagster-up            # Background service
make dagster-ui            # Print the URL (http://localhost:3001) and run it in the foreground
make dagster-logs          # Follow its logs
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

The module equivalent is a job: see [From Dagster to module jobs](/user-guide/build/modules/module-jobs#from-dagster-to-module-jobs).

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

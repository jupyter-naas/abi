---
sidebar_position: 2
title: "Module jobs"
---

# Module jobs

A **job** is work a module runs on a schedule, when an event happens, or when
someone triggers it. Jobs replace Dagster in a NATS project: the module declares
them and runs them in its own process, and JetStream schedules the triggers and
delivers them. There is no central scheduler, so adding a module needs no
orchestrator restart.

:::note NATS projects
Jobs need NATS, which is the default of `abi new project`. In a project without
NATS (legacy), a declared job is logged and not run: use
[Dagster](/user-guide/build/applications/dagster) there, or
[move the project to NATS](/user-guide/upgrade/migrate-to-3).
:::

## Declare a job

In a remote module (what `abi new module` creates), import from `naas_abi_sdk.jobs`:

```python
from datetime import timedelta
from naas_abi_sdk import BaseModule
from naas_abi_sdk.jobs import Cron, Every, JobContext, job


class ABIModule(BaseModule):
    @job(triggers=(Every("1h"),), timeout=timedelta(minutes=5))
    async def heartbeat(self, ctx: JobContext) -> dict:
        ctx.log("alive")
        return {"ok": True}  # kept on the run record

    @job(triggers=(Cron("0 0 2 * * *", time_zone="Europe/Paris"),), max_attempts=3)
    async def nightly_report(self, ctx: JobContext) -> None:
        if not await self.has_new_data():
            ctx.skip("nothing new")
            return
        ...
```

A module that the engine loads (`abi new module --in-engine`) declares them the
same way, from `naas_abi_core.module.jobs`; its handlers can also be plain
functions, which run in a worker thread.

A generated remote module already has a `heartbeat` job in `jobs.py`: start from it.

### A workflow or a pipeline as a job

In a remote module, a workflow or pipeline class becomes a job when it declares job
settings, with no handler to write: the module hosts a job named `<kind>.<name>`
(`workflow.digest_workflow`) that validates its payload into the parameters model and
runs the class.

```python
from naas_abi_sdk.jobs import Every, JobSettings

class DigestWorkflow(Workflow[DigestWorkflowParameters]):
    job = JobSettings(triggers=(Every("1h"),), timeout=timedelta(minutes=10))
```

`JobSettings()` alone means it runs only when someone starts it, from another module with
`await engine.modules[id].get_workflow(name).trigger({...})`, or the System app's **Run now**.
A `Cron` or `Every` trigger needs parameters that all have defaults, since a scheduled run
sends `{}`. The run record's result is the workflow's JSON or the pipeline's graph as
N-Triples, up to 64 KiB. See [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module#5-add-a-workflow-a-pipeline-or-an-integration).

## Triggers

| Trigger | Fires |
|---|---|
| `Every("30s")`, `Every(timedelta(hours=1))` | On a fixed interval, at least one second. |
| `Cron("0 30 9 * * mon-fri", time_zone="UTC")` | On a cron schedule: **six fields, seconds first**, or an alias such as `@daily`. `time_zone` is optional. |
| `OnEvent(event_type=<IRI>, filter={...})` | When an ABI event of that type happens, optionally filtered on its fields. |
| `OnEvent("<subject>")` | On any message on a NATS subject. |
| Manual | From the System app (**Run now**), from code, or with `POST /api/admin/system/jobs/<module>/<job>/trigger`. |

A job takes up to 16 triggers and these options:

| Option | Default | Meaning |
|---|---|---|
| `max_concurrency` | 1 | Runs at once, across all replicas. The default never overlaps a run with the next. |
| `timeout` | none | After it, `ctx.cancelled` is set and the run ends `TIMED_OUT`. |
| `max_attempts` | 1 | Attempts before the run fails. |

## What a handler gets

A handler receives a `JobContext`:

- `ctx.payload`: what the trigger carried (the JSON of a manual run, the event).
- `ctx.log(message)`: a line on the run's log, shown in the System app.
- `ctx.skip(reason)`: ends the run as `SKIPPED`, for a poll with nothing to do.
- `ctx.cancelled`: an event to check in a long loop; it is set on a timeout or a
  cancel.
- `ctx.run_id`, `ctx.job`, `ctx.attempt`, `ctx.trigger`.

What the handler returns is stored on the run record. An exception fails the
attempt, and the next one starts after a backoff while `max_attempts` allows.

## Run one by hand

The fastest check is the Nexus **System** app: its **Jobs** tab lists every job
of the engine and of the modules that registered, with a **Run now** button that
takes a JSON payload, and the history of each run: status, attempts, logs,
result and error.

From code, a module triggers its own jobs:

```python
run = await self.atrigger_job("nightly_report", {"day": "2026-10-19"},
                              idempotency_key="report-2026-10-19")
```

Use `self.trigger_job(...)` from synchronous code. Both raise `JobsNotHosted`
until the module has started, and always when NATS is off.

## Write handlers that can run twice

Delivery is **at least once**: after a crash, or a lost acknowledgement, a
handler can run again. Make it safe to repeat (write to a key, not append).

- An `idempotency_key` on a manual trigger deduplicates it for two minutes: the
  same key returns the same run.
- A missed cron tick fires once when the broker comes back, not once per tick
  that was missed. A daylight saving change can skip or repeat a tick.
- `OnEvent` is at most once: an event published while nothing hosts the job is
  lost.

Run records stay for 7 days (skipped ones for 1 hour), at most 1,000 per job.
Retries, timeouts, lost runs and shutdown are in
[Remote modules and jobs](/developer-guide/architecture/remote-modules#module-jobs).

## Jobs the engine runs itself

In NATS mode the engine hosts jobs for its own upkeep: dataset compaction and
cleanup, pruning agent memory, and the two migration jobs
(`agent_memory_migrate`, `activity_log_migrate`) you run once when you
[migrate from 2.x](/user-guide/upgrade/migrate-to-3). They show in the same
Jobs tab under the `naas_abi_core.*` modules.

## From Dagster to module jobs

Move each Dagster orchestration to a job before you switch a project to NATS:
the NATS stack has no Dagster service, since a second engine cannot run next to
the API.

| Dagster | Module jobs |
|---|---|
| A schedule (`ScheduleDefinition`, `cron_schedule`) | `Cron(...)` (six fields, seconds first) or `Every(...)` |
| A sensor that polls | `Every(...)` with `ctx.skip(...)` when there is nothing to do, or `OnEvent(...)` |
| A job with tag concurrency limits | `max_concurrency` |
| Retries | `max_attempts` |
| Run history in Dagster's storage | Run records, in the System app's Jobs tab |
| One Dagster process importing every module | Each module's own process (or the engine) |

A Dagster schedule such as

```python
ScheduleDefinition(job=refresh_job, cron_schedule="0 2 * * *")
```

becomes

```python
@job(triggers=(Cron("0 0 2 * * *", time_zone="UTC"),), max_attempts=3)
async def refresh(self, ctx: JobContext) -> None:
    ...  # what the Dagster op did
```

The cron expression gains a leading seconds field. Pipelines and workflows stay
as they are: the job calls them.

Dagster itself stays available as a [legacy extra](/user-guide/get-started/legacy-mode)
for projects without NATS, and is removed in the next major.

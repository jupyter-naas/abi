---
sidebar_position: 2.2
title: "Remote Modules and Jobs"
---

# Remote Modules and Jobs

A **remote module** is an ABI module that runs in its own process, or its own
container, and reaches the engine only through NATS. It is built with
`naas-abi-sdk`, which depends on `naas-abi-proto`, `protobuf` and `nats-py`, and
never on `naas-abi-core`. It registers itself in [discovery](./nats#discovery);
the engine never imports it.

This page explains how remote modules and module jobs work. To write one, follow
[Build a remote module](/capabilities/sdk/build-a-remote-module).

## Engine modules and remote modules

| | Engine module | Remote module |
|---|---|---|
| Created by | `abi new module --in-engine` (the default in a project without NATS) | `abi new module` (the default in a NATS project) |
| Runs | Inside the engine process | In its own process: `abi dev up` (`dev.modules`), a Compose service, any supervisor |
| Listed in | `modules:` in the config | Discovery, at run time |
| Imports | `naas_abi_core` | `naas_abi_sdk` only |
| Calls services | Through the engine (NATS facades in NATS mode) | `self.engine.services.<name>`, async, declared services only |
| Offers | Agents, workflows, pipelines, integrations, ontologies, apps, jobs | Agents, apps, jobs |
| Scheduled work | Module jobs (NATS mode); Dagster orchestrations (legacy, NATS off) | Module jobs |

Both kinds coexist: a project keeps its engine modules and adds remote ones.
Remote modules suit work that should scale, restart or deploy on its own, or
that a team ships separately (`abi new module --standalone` creates a
repository of its own).

## What a remote module offers

A module publishes a descriptor in discovery: its agents, jobs, models and
apps, and the services and modules it depends on. Replicas of one generation
must declare the same descriptor.

### Agents

A module declares each agent with an `AgentDescriptor` carrying the
`agent.invoke.v1` capability, and binds a handler in `on_initialized`
(`self.expose_agent(name, handler)`). Nexus lists remote agents next to the
engine's, and other modules reach them through
`self.engine.modules["<module id>"].get_agent(name)`, which returns an
`AgentProxy` (`invoke`, `stream_invoke`, `submit`).

- A run is a durable record in the Document Service: it can be reattached
  after a lost reply (`agent.invocation(id).events(...)`), its status read, or
  cancelled (cooperatively).
- Repeating a submission with the same invocation id and the same input returns
  the stored run; changed input fails with `INVOCATION_CONFLICT`.
- A conversation runs one turn at a time (a conversation claim). A module
  process runs at most 200 agent runs at once, shared by every agent it hosts;
  a submission past that fails with `AGENT_BUSY`.
- A run stops after 300 seconds without new output
  (`run_module(..., agent_idle_timeout_seconds=...)`); there is no total limit.
- In the chat API (`POST /api/chat/stream`, `/api/chat/complete`), a remote
  agent is selected by its **id**; a name selects in-process agents only.

The SDK ships agents written like the engine's (`naas_abi_sdk.agents`:
`IntentAgent`, `AgentConfiguration`), with their memory in the engine's
Document Service (`document_memory`), so a conversation survives restarts and
is shared by replicas.

### Models

A module uses the models the engine registers: declare `model_registry`, then
`await registry.get_default_chat_model()` or `get_chat_model(<canonical id>)`.
The result's `.model` is a LangChain chat model that streams over NATS, with
tool calling and structured output; no provider credential reaches the module.
Install `naas-abi-sdk[models]` (or `[agent]`).

### Apps

A module serves web apps through Nexus, with no port of its own. See
[Remote apps and large payloads](./remote-apps).

### Jobs

Scheduled and event-driven work, described below.

## Module jobs

Module jobs replace Dagster. A module declares its jobs and runs them in its own
process; JetStream schedules and delivers the triggers. There is no central
scheduler: adding or removing a module needs no orchestrator restart, and each
module's jobs run where the module runs.

```python
from datetime import timedelta
from naas_abi_sdk.jobs import Cron, Every, JobContext, OnEvent, job

class ABIModule(BaseModule):
    ...

    @job(triggers=(Every("1h"),), timeout=timedelta(minutes=5))
    async def heartbeat(self, ctx: JobContext) -> dict:
        ctx.log("alive")
        return {"ok": True}  # stored on the run record

    @job(triggers=(Cron("0 0 2 * * *", time_zone="Europe/Paris"),), max_attempts=3)
    async def nightly_report(self, ctx: JobContext) -> None:
        if not await self.has_new_data():
            ctx.skip("nothing new")
            return
        ...
```

Engine modules declare jobs the same way (`naas_abi_core.module.jobs`); their
handlers may also be synchronous, and run in a worker thread.

### Triggers

| Trigger | Meaning |
|---|---|
| `Every("30s")`, `Every(timedelta(hours=1))` | A fixed interval (a Go duration, at least 1 s). |
| `Cron("0 30 9 * * mon-fri", time_zone="UTC")` | A cron expression with **six fields, seconds first**, or an alias such as `@daily`. `time_zone` is optional. |
| `OnEvent(event_type=<IRI>, filter={...})` | An ABI event of that type, optionally filtered on its fields. |
| `OnEvent("<subject>")` | Any message on a core NATS subject. |
| Manual | `self.trigger_job(...)`, another module's `get_job(...).trigger(...)`, the System app's **Run now**, or `POST /api/admin/system/jobs/<module>/<job>/trigger`. |

A job has up to 16 triggers, and these options:

| Option | Default | Meaning |
|---|---|---|
| `max_concurrency` | 1 | Runs at once across all replicas (1 to 64). The default never overlaps a run with the next. |
| `timeout` | none | Sets `ctx.cancelled` when it passes; the run ends `TIMED_OUT`. |
| `max_attempts` | 1 | Attempts before the run fails (1 to 100). |

Event filters are EventBridge-style dictionaries on the event's fields (dotted
paths; a scalar, a list, or `eq`, `ne`, `in`, `gt`, `gte`, `lt`, `lte`,
`prefix`, `suffix`, `contains`, `exists`). They are checked before a trigger is
published, so a filtered event writes no run at all:
`OnEvent(event_type=OBJECT_PUT, filter={"prefix": {"prefix": "naas/"}})`.

### Running and triggering

- A handler receives a `JobContext`: `run_id`, `job`, `attempt`, `trigger`,
  `payload`, `log(message)` (a bounded log on the run), `skip(reason)` and
  `cancelled` (an event to check in long loops).
- One replica takes each trigger: replicas share one durable consumer per job.
- A module triggers its **own** jobs with `self.trigger_job(name, payload,
  idempotency_key=...)` from sync code, or `await self.atrigger_job(...)`.
  Both raise `JobsNotHosted` before the job host starts (and always with NATS
  off).
- Another module's job: declare the module as a dependency, then
  `job = await self.engine.modules["<id>"].get_job(name)` and
  `run = await job.trigger(payload)`. `run.status()`, `run.wait()` and
  `run.cancel()` follow it. `ABIClient.get_job(module_id, name, project=...)`
  reaches any module's job by name, engine modules included.

### Idempotency and delivery

- Delivery is **at least once**: a handler may run again after a crash or a
  lost acknowledgement. Write handlers that tolerate a repeat.
- `idempotency_key` deduplicates manual triggers: within the jobs stream's
  duplicate window (2 minutes), a repeated key is the same trigger and returns
  the same run, with `JobRun.duplicate` set.
- A missed cron tick fires once when the broker comes back, not once per
  missed tick. Daylight saving changes can skip or repeat a tick.
- `OnEvent` is at most once from the event to the trigger: events published
  while no host runs are lost.

### Runs, failures and retention

Each trigger has one **run record** in the Document Service (collection
`job_runs_<hash>` in the module's namespace). Its status moves through
`QUEUED`, `RUNNING`, `RETRYING`, then one of `SUCCEEDED`, `SKIPPED`, `FAILED`,
`TIMED_OUT` or `CANCELLED`. It holds the attempts, the trigger, the payload,
the logs, the result and the error. The System app's **Jobs** tab shows them.

- **Failures.** An exception fails the attempt; the next attempt starts after a
  backoff while `max_attempts` allows. When the run's record cannot be read or
  written (store outage), the delivery is retried without using an attempt.
- **Trigger lifetime.** A trigger lives 1 hour (schedule ticks), 24 hours
  (events) or 7 days (manual). A run whose trigger expires before its retry is
  recorded `FAILED` ("Trigger expired before it could be retried").
- **Lost runs.** A run heartbeats every 10 s. One whose heartbeats stopped for
  5 minutes on its last attempt is recorded `FAILED` ("Lost: no heartbeat
  since ...").
- **Cancellation** is cooperative: `ctx.cancelled` is set. A synchronous engine
  job still running `nats.jobs.interrupt_grace_seconds` (5 s) later gets
  `JobInterrupted` raised in its thread; the run keeps its slot until the
  thread exits.
- **Shutdown** interrupts runs as failed attempts ("Interrupted by host
  shutdown"), so they run again while attempts remain.
- **Retention.** Skipped runs are kept 1 hour, other finished runs 7 days, and
  at most 1,000 finished runs per job (`nats.jobs.retention`). Queued, running
  and retrying runs are never pruned.

### The engine's own jobs

In NATS mode the engine hosts these jobs itself:

| Owner | Job | When |
|---|---|---|
| `naas_abi_core.dataset` | `dataset_compaction` | Daily, 02:00 UTC |
| `naas_abi_core.dataset` | `dataset_cleanup` | Daily, 03:00 UTC |
| `naas_abi_core.dataset` | `dataset_catalog_monitor` | Hourly |
| `naas_abi_core.agent_memory` | `agent_memory_prune` | Daily, 03:00 UTC |
| `naas_abi_core.agent_memory` | `agent_memory_migrate` | On demand |
| `naas_abi_core.activity_log` | `activity_log_migrate` | On demand |
| `naas_abi_core.event_archive` | `event_archive` | Hourly, at :30 (PostgreSQL event archive only) |

Every process that loads the engine in NATS mode hosts jobs, and the shared
consumers make each trigger run once. Set `nats.jobs.enabled: false` on a
one-off engine that should not take work.

### From Dagster to module jobs

| Dagster | Module jobs |
|---|---|
| A schedule (`ScheduleDefinition`, `cron_schedule`) | `Cron(...)` (six fields, seconds first) or `Every(...)` |
| A sensor that polls | `Every(...)` with `ctx.skip(...)` when there is nothing to do, or `OnEvent(...)` |
| A job with tag concurrency limits | `max_concurrency` |
| Retries | `max_attempts` |
| Run history in Dagster's storage | Run records, in the System app's Jobs tab |
| One Dagster process importing every module | Each module's own process (or the engine) |

Dagster stays available as a legacy extra for projects with NATS off; see
[Dagster](/capabilities/applications/dagster).

→ [Remote apps and large payloads](./remote-apps)

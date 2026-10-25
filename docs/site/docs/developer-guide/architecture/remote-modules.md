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
[Build a remote module](/user-guide/build/sdk/build-a-remote-module).

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

### Jobs and workflows

Scheduled and event-driven work, described below. A **workflow** is a job with a
typed input and output and checkpointed steps (see [Workflows](#workflows)).

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

### Workflows

A workflow is a job (`kind="workflow"` in its descriptor) with a typed input and
output, whose handler checkpoints its steps. If a host stops, a deploy rolls or a
step fails, the retry of the run returns the stored results of the steps that
finished and runs the rest. It uses the same consumer, run record, attempts,
cancel and retention as any job.

```python
from naas_abi_sdk.jobs import Cron
from naas_abi_sdk.workflows import FlowContext, workflow

class ABIModule(BaseModule):
    @workflow(
        triggers=(Cron("0 0 * * * *", input={"filter": "db"}),),
        max_concurrency=1,
        max_attempts=3,
    )
    async def tweets(self, ctx: FlowContext, inp: TweetsInput) -> TweetsOutput:
        files = await ctx.step("fetch", self.fetch, inp, retries=2)
        await ctx.map_call("map", "acme.tweets", "map_envelope", [{"path": f} for f in files])
        await ctx.step("publish", self.publish_app)
        return TweetsOutput(count=len(files))
```

`TweetsInput` and `TweetsOutput` are pydantic v2 models (their JSON Schemas go in
the descriptor, so Nexus and callers see them), or `dict` with
`input_schema=`/`output_schema=`. The SDK does not depend on pydantic. The input
is validated before the handler runs; an invalid one fails the run without a
retry. In an SDK module, declare workflows only on async methods;
`declare_workflow(name, handler, input_type=..., output_type=...)` declares one at
runtime (in `on_load`). Engine modules may also write sync workflows (below).

| `FlowContext` | What it does |
|---|---|
| `await ctx.step(key, fn, *args, retries=0, backoff=1.0, **kwargs)` | Runs `fn` (async, or sync in a thread) once for the run and stores its JSON result. A later attempt returns the stored result without calling `fn`. `retries` local attempts follow a failure. |
| `await ctx.map(key, items, fn, concurrency=8)` | `step` per item, in this process; item `i` is `key[i]`. |
| `await ctx.call(module_id, workflow, input, key=None)` | Runs another module's workflow as a child run and returns its output. |
| `await ctx.map_call(key, module_id, workflow, inputs, concurrency=8)` | One child run per input, on whichever replica takes each. |

Rules that keep a replay correct:

- **Step keys** are unique within a run and the same on every attempt: derive them
  from the input, not from time or randomness. `map` and `map_call` need their
  items in the same order each time, so take them from an earlier step.
- A step result is JSON, at most **256 KiB**; the error says to store large data in
  object storage and return a reference. A run record keeps at most 64 KiB of the
  output.
- **Child runs** are journaled before the parent waits: a replay waits for the
  same run instead of starting another. The child is triggered with an
  idempotency key, but JetStream deduplicates only within 2 minutes, so a parent
  that dies between triggering and journaling, and replays later, can start a
  second child: make child workflows idempotent.
- A parent keeps its concurrency slot and its heartbeats while it waits. Cancelling
  it cancels the children it waits for. A workflow that calls itself is refused.
- Long waits (`sleep`, waiting for an event or an approval) are not supported yet.

A `Cron` or `Every` trigger can carry an `input` (a JSON object of at most 4 KiB):
the run's payload on each tick. Changing it publishes that schedule again;
unchanged schedules, and their intervals, are left alone.

To call a workflow: `ABIClient.get_workflow(module_id, name, project=...)`,
`await self.engine.modules["<id>"].get_workflow(name)` or `self.get_workflow(name)`
for the module's own. `await wf.run(input)` returns the output;
`run = await wf.start(input, idempotency_key=...)` returns a handle with
`status()`, `wait()`, `result()`, `steps()` (key, status, attempt, timings, errors
and child run ids of each step, without results) and `cancel()`. Hosts publish a
completion notice when a run ends, so `wait()` does not poll hard; polling every
5 seconds stays as the fallback. See
[ADR: durable workflows on NATS](https://github.com/jupyter-naas/abi/blob/main/docs/adr/20261025_durable-workflows-on-nats.md).

#### Engine modules and the Workflow/Pipeline bridge

Engine modules (core `BaseModule`) get the same workflows, from
`naas_abi_core.module.workflows`. Async handlers are the SDK's. A sync handler runs
in a worker thread, like a sync job, and receives a `SyncFlowContext` with blocking
`step`, `map`, `call` and `map_call`:

```python
from naas_abi_core.module.workflows import SyncFlowContext, workflow

class ABIModule(BaseModule):
    @workflow(max_attempts=3)
    def report(self, ctx: SyncFlowContext, inp: ReportInput) -> ReportOutput:
        rows = ctx.step("load", self.load, inp.table)
        ctx.map_call("push", "acme.sink", "push", [{"row": r} for r in rows])
        return ReportOutput(count=len(rows))
```

A step function runs in the handler's own thread, so a run that times out or is
cancelled is interrupted like a sync job. `self.get_workflow(name)` calls the
module's own workflow; `engine.modules["<id>"].get_workflow(name)` another engine
module's; `self.engine.get_workflow("<module id>", name)` any module by id, remote
ones included (declare a remote module as a `#soft` dependency).

With `nats.workflows.bridge` on (the default), every `Workflow` and `Pipeline`
instance of an engine module that has a live typed `run()` (the ones that get a
`POST /workflows/<slug>` or `/pipelines/<slug>` route) is also published as a
one-step workflow, `workflow.<slug>` or `pipeline.<slug>`, with the parameters
model as its input schema and the class docstring as its description. It runs with
`max_concurrency=1` and `max_attempts=1`, because pipelines write to the graph. An
rdflib `Graph` result comes back as `{"format": "text/turtle", "triples": n,
"data": "<turtle>"}`, with `data` left out when it would not fit in a run record.
The classes, their agent tools and their REST routes do not change; without NATS
nothing is published.

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
[Dagster](/user-guide/build/applications/dagster).

→ [Remote apps and large payloads](./remote-apps)

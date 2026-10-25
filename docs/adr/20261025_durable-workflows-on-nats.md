# Durable workflows on NATS

## Status
Accepted. Step 1 (proto and SDK runtime), step 2 (engine modules and the
`Workflow`/`Pipeline` bridge) and step 4 (the port of X) implemented. Nexus
(System → Jobs and `/api/workflows`) builds on them and follows.

## Date
2026-10-25

## Context
Module jobs (`docs/adr/20261001_nats-jobs.md`) run one handler per trigger, with
retries but no memory between attempts: a retry of a long job repeats everything
it did. Real orchestrations are multi-step (fetch, fan out, publish), call other
modules, and must not redo finished steps after a crash or a deploy. They still
run in Dagster (legacy, NATS off), or as `Workflow`/`Pipeline` classes called
in-process with no typed contract and no way to launch or watch them.

Jobs already give the hard parts: one durable consumer per job, run records with
CAS, attempts counted on the record, `nak` backoff, cooperative cancel,
idempotency keys, retention, heartbeats, discovery and the Nexus Jobs tab.

## Decision
**A workflow is a job with a schema and a journal.** It reuses the jobs runtime
unchanged and adds four things.

### Descriptor
`JobDescriptor` (proto `abi.discovery.v1.JobDescriptor`, tags 8 to 10) gains
`kind` (`"job"`, or `"workflow"`), `input_schema` and `output_schema` (JSON Schema
objects as canonical strings: sorted keys, so replicas declare identical bytes).
A descriptor written before the fields existed decodes with `kind="job"`.
`JobTrigger` gains `input` (tag 5). Descriptors travel in discovery's registry
snapshot (512 KiB for every module), so they are bounded, in the SDK when a
descriptor is built: a schema is at most 16 KiB, a trigger input at most 4 KiB,
a whole descriptor at most 64 KiB (`ValueError` naming the limit). Link to docs
for what does not fit; do not inline it in a schema.

### Trigger inputs
`Cron(..., input={...})` and `Every(..., input={...})` carry a JSON object. It is
the schedule message's body (it was always `b"{}"`), so each tick's run gets it
as its payload. A schedule with an input also has an `Abi-Job-Input-Hash` header,
which joins `SCHEDULE_HEADERS`, so a changed input is a changed schedule that is
published again, while unchanged schedules are left alone (replacing an
`@every` message restarts its interval, which is what the existing rule avoids).
The header is only set when there is an input: schedules published before this
change have none, compare equal to an input-less schedule, and are not
republished by the upgrade. An empty input is no input.

### `@workflow` and runtime declaration
`@workflow(name=None, description=..., triggers=..., max_concurrency=1, timeout=...,
max_attempts=...)` on an async module method
`(self, ctx: FlowContext, inp: In) -> Out` declares a `kind="workflow"` job. `In`
and `Out` are pydantic v2 models, duck-typed (`model_json_schema`, `model_validate`,
`model_dump`: pydantic stays an optional dependency and nothing imports it), or
`dict` with an optional `input_schema=`/`output_schema=` (default for a dict
input: `{"type": "object"}`; an unannotated or non-model output has no schema).
The input is validated before the handler runs; an invalid input raises
`InvalidWorkflowInput`, a `NonRetryable`, and the run fails at once whatever
`max_attempts` says. `NonRetryable` is general: the job host turns any such
exception into FAILED without a retry.

`JobsMixin.declare_job(descriptor, handler)` and `declare_workflow(name, handler,
input_type=..., output_type=..., ...)` declare a job at runtime, for jobs not known
when the class is written (core's bridge). They apply to the module instance, and
raise `JobsSealed` once the module's jobs went to its job host. For an SDK module
`run_module` takes the descriptor discovery shows after `on_load`, so declare
there; jobs declared later are refused with an error, as replicas of a rollout
must declare identical sets and discovery enforces it.

### `FlowContext` and the journal
`FlowContext` extends `JobContext`; the host builds it for `kind="workflow"` jobs.
- `step(key, fn, *args, retries=0, backoff=1.0, **kwargs)` runs `fn` (async, or sync
  in a thread) and journals its result. A journaled success returns the stored
  result and does not call `fn`. `retries` local attempts follow a failure, with
  exponential backoff; the exception then reaches the handler and the step is
  recorded FAILED (it runs again when the run is retried; attempts keep counting).
  The returned value is the JSON that a replay returns, also on the first run.
- `map(key, items, fn, concurrency=8)` is in-process fan-out; item `i` is the step
  `key[i]`.
- `call(module_id, workflow, input, key=None)` and `map_call(key, module_id, workflow,
  inputs, concurrency=8)` start child runs with `JobProxy` and return their outputs.

The journal has two collections in the module's document namespace:
`workflow_steps_<hash(project)>`, one small summary per (run, step key) (status,
attempt, timings, error, child run reference) listed for UIs without loading any
result, and `workflow_results_<hash(project)>`, the JSON text of each step result
(a string, so floats and big integers survive the document store). Documents are
`<run id>#<step key>`. A result is written before the summary that says SUCCEEDED,
so a succeeded summary always has its result. Writers use CAS. A summary records
the run's `fired_at`; one written for another trigger of the same run id (a
recreated jobs stream reuses sequences) is ignored. Retention deletes a run's
journal with its record.

Guards: a step result is JSON and at most 256 KiB, else `StepResultTooLarge` says to
store large data in object storage and return a reference. A step key is unique
within a run (`StepKeyError` otherwise; in memory, per attempt), at most 200
characters. A fan-out has at most 10,000 items. A run that calls its own workflow
(same module and name) is refused with `SelfCall`: its child would wait for the
slot its parent holds. Indirect cycles (A calls B calls A) are not detected.

### Child runs
`call` journals the child's run id **before** it waits. On a replay, a step that
is RUNNING with a child run id waits for that run instead of triggering another,
and a SUCCEEDED step returns its stored output without waiting. The trigger carries
the idempotency key `<run id>/<step key>/<step attempt>`, so a host that died before
journaling the child id triggers the same message again, which JetStream drops
inside its 2 minute duplicate window. A child that ended FAILED, TIMED_OUT or
CANCELLED fails the step (`ChildRunFailed`); the next attempt of the parent starts a
new child, with the next step attempt number. A child's output over the job host's
result cap (64 KiB) arrives as a truncated marker: `ChildOutputTruncated`, return a
reference instead.

A parent keeps its concurrency slot while it waits for children, and its
acknowledgement and progress heartbeats keep running, as for any run. Cancelling
the parent (`ctx.cancelled`) stops its waits; once its run ends CANCELLED, the host
asks each child it still waits for to cancel (`FlowContext.finish`). A host
shutdown or a timeout does not cancel children: the retry re-attaches to them.

### Completion notices
When a host saves a terminal run (also when its upkeep fails a lost run), it
publishes a core-NATS notice, `{"run_id", "status"}`, on the job's
`abi.jobdone.<project>.<h(module)>.<h(job)>` subject. The subject is outside the
jobs stream's `abi.jobs.<project>.>`, so no notice is stored. `CompletionNotices`
(used by `WorkflowRun.wait`/`result` and by parents waiting on children) keeps one
subscription per job and wakes the waiters of that run id. Core NATS is
at-most-once, and a notice can be missed (a restart, a slow consumer), so every
wait also reads the run record every 5 seconds; a notice only shortens the wait.
If subscribing fails, waits poll.

### Nexus
System → Jobs lists workflows beside jobs (`kind`, schemas and trigger inputs from
both catalogs), launches them from a form generated from the input schema, and
shows each run's steps with links to its child runs. `/api/workflows` lists, starts
(`?wait`, `Idempotency-Key`), reads and cancels runs. The API validates the input
against the schema before anything is triggered (422, nothing audited or sent); a
schema it cannot use accepts everything, because the module validates its own
input. Access is a super admin's session or `ABI_API_KEY` (a new dependency,
`require_superadmin_or_api_key`, `Authorization` header only): the key is the
instance's shared operator key, so it now also reaches these routes. Starts and cancels are audited like job triggers (service
`jobs`) before they happen, with how the caller authenticated; a key caller has no
user, so its `audit_logs.user_id` is NULL and `details.via` is `api_key`.

### Calling
`WorkflowProxy(start(input, idempotency_key=None) -> WorkflowRun, run(input,
timeout=None) -> output)`; `WorkflowRun(status(), wait(), result(), steps(),
cancel())`. `ModuleProxy.get_workflow(name)` (discovery; a plain job is not a
workflow), `ABIClient.get_workflow(module_id, name, project=...)` (by name, engine
modules included), and `self.get_workflow(name)` for a module's own workflows,
through its bound host (it runs on the host's loop; `JobsNotHosted` outside).
`input_type=`/`output_type=` check the input before it is sent and return the output
as a model; `self.get_workflow` passes the module's declared types.
`get_job` keeps working on workflows. `steps()` returns the summaries in start order.

### Engine modules
Core `BaseModule` gets workflows through `naas_abi_core.module.workflows` (a sibling
of `module/jobs.py`, with the same inert fallback when `naas-abi-sdk` is not
installed). Hosting is the jobs path: `EngineJobLoader` already hosts every module
with `jobs`, so a workflow, declared on a class or at runtime, needs nothing more,
and a declared one without a handler fails `Engine.load` as a job does. The loader
gives each host a `module_documents` resolver over the engine's own document
namespaces, which is how a workflow reads the run records of its children.

**Sync handlers.** Engine code blocks, so `@workflow` also accepts a plain `def`
(`declare_workflow` a sync callable). It runs in a worker thread (`SyncJobRunner`),
and gets a `SyncFlowContext` whose `step`, `map`, `call`, `map_call` and `steps`
submit the `FlowContext` call to the host's loop (in a copy of the thread's context,
so the journal's service calls nest under the run's trace span) and block, waking
every 200 ms so that `JobInterrupted` can land. Two choices:
- A **`step` function runs in the handler's own thread**, not in a pool: the journal
  work happens on the loop and the function runs where an interrupt reaches it, so
  a run stopped by a timeout or a cancel keeps its concurrency slot until the
  function has returned, as a sync job does. (The loop-side step waits for the
  function through a queue the handler thread serves.)
- **`map` items run on worker threads of the call**, `concurrency` at a time, each
  item a step `key[i]` that again runs in its own thread. `JobInterrupted` does
  not reach them: the call returns only after its workers finish, and long item
  functions look at `ctx.cancelled`.
`ctx.cancelled` and the grace behaviour are unchanged. A skipped run (`ctx.skip`)
returns no output, as for async workflows. Async handlers are the SDK's, unchanged.

**Calling.** `module.get_workflow(name)` (the SDK's, through the module's bound host)
works on any engine module's instance, so `engine.modules[m].get_workflow(name)`
reaches another engine module. A module is not in `engine.modules` unless the
engine runs it, and remote modules are not (their ids are `#soft` dependencies the
engine does not require), so `EngineProxy.get_workflow(module_id, name)`
(`Engine.workflow`, `EngineJobLoader.workflow`) returns a `WorkflowProxy` for any
module by id on the engine's connection and the loader's loop, for declared
dependencies only. It works on engines that host nothing (a client, a CLI), which
then only start and watch runs, and, like `ABIClient.get_workflow`, it checks nothing
until a start. Its methods are coroutines, awaitable from any loop (sync code uses
`asyncio.run`).

### The Workflow/Pipeline bridge
With `nats.workflows.bridge` (new engine config, default `true`), `Engine.load`
declares each instance in an engine module's `workflows` and `pipelines` that has a
live typed `run()` as a one-step workflow, after `on_initialized` (the instances
exist) and before `EngineJobLoader.start` (the descriptors are sealed then):
- **Which.** The `register_run_route` predicate, extracted as
  `process_api.process_parameters_type`: `run()` is a real override that is not a
  `pass` or `raise NotImplementedError` stub, and a pydantic parameters model is
  found. About 22 of the 60 classes qualify. An async `run()` is skipped, as are
  names already taken in the module. Others are skipped with a debug log.
- **Name and descriptor.** `workflow.<slug>` or `pipeline.<slug>` with
  `process_route_slug`, the slug of the REST route. The input schema is the
  parameters model. The description is the class's own docstring (`getdoc` would
  give a subclass without one the base class's text). The output schema comes from
  the return annotation (a model, a dict, the graph envelope), else none.
  `max_attempts=1`: a pipeline writes to the graph, and a retry would write twice.
  `max_concurrency=1`: durable runs of one class do not overlap (a REST call or an
  agent tool can still run the same instance at the same time).
- **Handler.** The input is validated (invalid: `InvalidWorkflowInput`, no retry),
  then `run(params)` is the one step `run`, in the worker thread. The step is
  journaled, so the timeline shows it, and its result is the encoded result.
- **Result.** The step journal takes only strict JSON, and `run()` has done its work
  by the time it is encoded, so the result is normalized first, the way the REST
  route sends it: containers are walked, leaves go through FastAPI's encoder
  (models, datetimes, paths, decimals, sets, enums, dataclasses), NaN and infinity
  become `null`, anything else becomes its text. An rdflib `Graph` becomes
  `{"format": "text/turtle", "triples": n, "data": "<turtle>"}`, with `data` dropped
  for a `note` when the Turtle is over **60 KiB**. Every other result over 60 KiB
  of JSON becomes `{"omitted": true, "bytes": n, "limit": n, "note": ...}` instead.
  The cap is the run record's (64 KiB, a larger output comes back as a truncation
  marker that does not validate against the advertised schema), not the step's
  256 KiB. The declared output schema is the return model's or `anyOf` it and the
  marker. We return a marker rather than fail the run (`NonRetryable`): the pipeline
  has already written its triples, and a failed run invites a re-launch that writes
  them twice. Most pipelines insert into the triple store themselves, so the result
  is a courtesy.
- **Everywhere.** The bridge runs in every NATS engine, whether it hosts or not, so
  `Engine.job_owners()` lists the same jobs in the API process and in the serving
  engine. Without NATS, or with the switch off, nothing is declared.
- **Unchanged.** The classes, `as_tools`, `as_api` and the `/workflows` and
  `/pipelines` routes keep calling `run()` in-process.

### The first real use: X on workflows

The X application's recent-tweets flow (`applications/x`, `AGENTS.md` there) runs as
workflows and jobs under NATS, with no Dagster process; its Dagster orchestrations are
kept for `--without-nats`, and both call the same bodies (`x/flows/common.py`, none of
which imports Dagster).
- **Search.** `search_recent_tweets` (input `{"filter": name}`) has one `Cron`/`Every`
  trigger per configured filter, carrying the filter name as its input. Steps: overlap,
  spend guard, fetch and save, `map_call` of `map_tweet_envelope` over the envelopes it
  saved, a `call` of `count_recent_tweets` when the filter follows counts, dataset sync,
  app publish. A retry after the fetch does not call the X API again and re-attaches to
  its mapping children.
- **Not on `OnEvent`.** The Dagster sensor mapped envelopes from `ObjectPut` events with
  a durable cursor; `OnEvent` is at-most-once, so the search run hands the envelopes it
  saved to the mapping workflow itself. The mapping is idempotent (an envelope that is
  gone, or already in the graph and the dataset, ends SKIPPED), and
  `reprocess_tweet_envelopes` (manual) re-maps a prefix and is a no-op the second time.
- **Overlap is skipped, not queued.** `max_concurrency` queues a tick behind the runs in
  the slots, which is wrong for a poller. A tick whose previous run of the same filter
  is `RUNNING` or `RETRYING` ends SKIPPED, decided from the job's run records in a
  journaled step. Only a run that started earlier (a lower stream sequence) blocks, so
  two ticks that start together do not both skip. The job's `max_concurrency` is its
  number of filters, so filters run side by side.
- **Triggers from configuration.** A workflow declared with `@workflow` has static
  triggers; X's come from its configuration, so `search_recent_tweets` is declared at
  load with `declare_workflow` (a descriptor holds 16 triggers: more filters declare
  `search_recent_tweets_2`, and so on). The configured cron keeps Dagster's dialect and
  is converted to NATS's (seconds first).
- **Jobs.** The hourly app build and the six-hourly compaction are `@job`s with the same
  schedules, and skip a tick whose previous run is still going.
- **Consequence.** Envelopes saved by other callers (the X agent's tools, scripts) are no
  longer mapped automatically under NATS; `reprocess_tweet_envelopes` maps them.

### Discovery
Core's discovery service validates the new descriptor fields with the SDK's
bounds: `kind` is `job` or `workflow` (empty, from before the field, is a job),
schemas and trigger inputs are JSON objects of at most 16 KiB and 4 KiB, a whole
job descriptor at most 64 KiB. Replica equality already covered the new fields.

## Consequences
- **Children are at-least-once.** Deduplication covers only the window before the
  child run id is journaled, and only inside JetStream's 2 minute duplicate window;
  a host that dies, is slow to restart, and replays later than that can start a
  second child for that step. Child workflows should be idempotent, like any job.
  After the id is journaled the replay always re-attaches.
- **Step keys must be deterministic.** Keys name journal entries, and a replay maps
  steps by key. Computing a key from time, randomness or a set's order makes the
  replay miss its journal and run the step again (not wrong, but not durable);
  `map` and `map_call` need their items in the same order on every attempt, so
  take them from an earlier step. Changing a workflow's step keys while runs are in
  flight makes those runs redo the renamed steps.
- **A parent holds its slot while it waits.** A workflow that waits on children of
  a job with a smaller `max_concurrency` than its own fan-out simply waits; a
  cycle through two workflows can deadlock (not detected, only the direct
  self-call is refused). Size `max_concurrency` for the number of parents that
  wait at once.
- **Long waits are future work.** `sleep`, `wait_for_event` and human approval
  would hold a slot for hours. They need a run that parks (releases its slot and
  is woken by a timer or an event), which the journal and the run record already
  allow but this change does not build.
- A cancelled parent cancels the children **it is waiting for**. A child already
  triggered but not yet started by any host still starts and runs; cancel reaches
  only running handlers (as for any job). A fan-out that stops on a failure leaves
  the children it started running; its journal keeps their ids, and a retry
  re-attaches.
- **Skipping.** A workflow that calls `ctx.skip(reason)` and returns `None` ends
  SKIPPED, whatever its output type (the handler lets `None` through only then).
  A skipped run has no output: `WorkflowRun.result()` returns `None`, and a parent's
  `call` gets `None` (journaled as a succeeded step with a `null` result). Callers
  that need to tell a skip from a result read `status()`.
- A parent that replays after its child's run record was pruned (7 days by
  default, or 1 hour for a skipped run) finds no record, which reads as QUEUED, and
  waits until the parent's timeout. A retry that late is unlikely; set `timeout`.
- Step keys have no control characters (a child's idempotency key, which includes
  the key, is a message id header). Keys built from data should be hashed or sanitized.
- A model instance returned by a typed workflow must be of the declared output
  class; a dict is validated into it.
- A failed step is journaled FAILED and runs again when the run is retried; the
  completed steps before it are kept. With `max_attempts=1` a failed run is
  not retried at all: set `max_attempts` for workflows that should resume.
- Step results are JSON. A replay returns the same JSON the first run returned,
  so a step that returns a model returns a dict on both. The cap is 256 KiB per
  result, and a run record keeps at most 64 KiB of its output (the host's cap).
- The journal is two documents per step, and three writes for a step that
  succeeds (start, result, summary). A workflow with thousands of tiny steps
  should batch them into fewer steps, or use `map` over items with real work.
- Core's discovery validates `kind`, the schemas and the trigger inputs against these
  bounds as well as the SDK, so a hand-written descriptor cannot exceed them.
- Hosts of engine modules need the notice subject: the broker's `module` user may
  publish and subscribe on it (its deny lists name only the engine's own subjects).
- Not hosted without NATS, like jobs.
- **Engine modules.** A sync `step` function blocks the handler's thread but not the
  host's loop; a `map` of sync items uses threads that an interrupt does not reach.
  A step function cannot be cancelled in the middle of a blocking C call, as for
  sync jobs.
- **The bridge adds a concurrency limit and a retry limit the classes never had.**
  Two launches of the same bridged pipeline run one after the other
  (`max_concurrency=1`), and a failed run is not retried (`max_attempts=1`). In-process
  callers (agent tools, REST) are not limited. A bridged pipeline that a REST call and
  a workflow run write with at the same time is not serialized across the two paths.
- A graph result over 60 KiB comes back without its Turtle, only the triple count and a
  note. Any other bridged result over 60 KiB of JSON comes back as the `omitted` marker
  (`bytes`, `limit`, `note`), and the run still succeeds: callers that need the data read
  what `run()` wrote (the triple store, object storage), or call a workflow that returns a
  reference. A caller that validates the output as a model (`output_type`, `ctx.call`
  into a typed consumer) must accept the marker.
- The bridge is evaluated once per engine start, from the instances `on_initialized`
  built. A class that could not be instantiated has no workflow. Changing a class's
  parameters model changes its input schema on the next start; there is no schema
  version.
- **`ABI_API_KEY` reaches `/api/workflows`.** It was a credential for agents and
  `/app-html/`; a script holding it can now also start and cancel workflow runs, as
  an operator. Rotating the key revokes both. Its calls are told apart in the audit
  log (`via: api_key`), not by person.
- Nexus reads a run's steps from the module's document namespace and does not wait
  on completion notices: `?wait` polls the run record (every 0.2 s, backing off to
  1 s, at most 120 s). A run no host has recorded yet reads as QUEUED for any run id
  of an existing workflow, so a mistyped sequence number reads as queued rather
  than missing.

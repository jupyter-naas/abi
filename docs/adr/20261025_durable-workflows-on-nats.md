# Durable workflows on NATS

## Status
Accepted. Step 1 (proto and SDK runtime) implemented. Engine modules and the
`Workflow`/`Pipeline` bridge, Nexus (System → Jobs and `/api/workflows`) and the
port of X build on it and follow.

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
- Core's discovery validates job descriptors; it does not yet check `kind`, the
  schemas or trigger inputs against these bounds. The SDK enforces them when a
  descriptor is built, so only a hand-written descriptor can exceed them.
- Hosts of engine modules need the notice subject: the broker's `module` user may
  publish and subscribe on it (its deny lists name only the engine's own subjects).
- Not hosted without NATS, like jobs.

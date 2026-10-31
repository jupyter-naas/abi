# Module loaders

> Scope: `libs/naas-abi-core/naas_abi_core/module/`. How a module discovers its components.

## Purpose

`BaseModule` is the unit of composition. `on_load` walks folders. `on_initialized` constructs what it can. The kernel API then calls `as_api` on the instances.

## Files

| File | Role |
|---|---|
| `Module.py` | `BaseModule` lists and lifecycle |
| `ModuleAgentLoader.py` | `agents/*.py` → `Expose` subclasses |
| `ModuleOrchestrationLoader.py` | `orchestrations/*.py` |
| `ModuleModelLoader.py` | `models/` → model registry |
| `ModuleComponentLoader.py` | Shared recursive folder walk |
| `ModuleWorkflowLoader.py` | `workflows/` → `Workflow` subclasses |
| `ModulePipelineLoader.py` | `pipelines/` → `Pipeline` subclasses |
| `ModuleToolLoader.py` | `tools/` → `Expose` and `BaseTool` subclasses |
| `jobs.py` | Job API (`job`, `JobDescriptor`, `Cron`, `Every`, `OnEvent`, `JobContext`), shared with the SDK; `JobsMixin` adds sync workflow handlers |
| `workflows.py` | Workflow API (`workflow`, `FlowContext`, `SyncFlowContext`, `WorkflowProxy`, `WorkflowRun`), shared with the SDK |
| `jobs_fallback.py`, `workflows_fallback.py` | Inert stand-ins when `naas-abi-sdk` is not installed |
| `../utils/process_api.py` | `instantiate_process`, default `run()` POST |

## Lifecycle

1. `on_load`: discover classes. Do not touch other modules or services.
2. `on_initialized`: `instantiate_all` on workflow, pipeline, and tool classes. Call `super().on_initialized()` if you override this hook.
3. Kernel `_load_runtime_routes`: agents via `New()` + `as_api`; processes via `mount_module_processes`.

Optional marketplace keys belong on the module, not in `{{ secret.NAME }}` YAML. Set `optional_secrets = True` and `secret_fields = {"config_field": "ENV_NAME"}`. `EngineModuleLoader` calls `ABIModule.build_configuration` at load: a present secret is copied in, a missing one uses the field default, and `Engine.load` continues. `{{ secret.NAME }}` in YAML still fails the whole engine when the key is absent.

A class that needs constructor config we cannot supply is skipped and logged. That is intentional. Do not invent a fake instance.

## Jobs

Declare `jobs` or decorate methods with `@job(triggers=(Cron(...),))` from `naas_abi_core.module.jobs`. Bind other handlers with `expose_job` in `on_initialized`. Handlers take a `JobContext` and may be sync (run in a worker thread) or async. In NATS mode the engine hosts them (`engine_loaders/EngineJobLoader.py`). Every declared job needs a handler, or `Engine.load` fails. Handlers must be idempotent: delivery is at-least-once. A sync handler that times out or is cancelled gets `ctx.cancelled`, then `JobInterrupted` in its thread after `nats.jobs.interrupt_grace_seconds` (`SyncJobRunner`); check `ctx.cancelled` in long loops and set I/O timeouts. Never catch `BaseException` broadly in job code. A module triggers its own jobs with `self.trigger_job(name, payload, idempotency_key=...)` (sync code, e.g. a request thread) or `await self.atrigger_job(...)`, once its host runs (`JobsNotHosted` otherwise). `ctx.skip(reason)` marks a run that had nothing to do (SKIPPED, pruned after an hour; finished runs are kept 7 days or 1,000 per job, `nats.jobs.retention`). `OnEvent(event_type=..., filter={...})` only triggers on matching events. See `docs/adr/20261001_nats-jobs.md`.

## Workflows

A workflow is a job with a typed input and output whose handler checkpoints its steps (Decision (2026-10-25) below, SDK side in `libs/naas-abi-sdk/AGENTS.md`). It runs on the jobs runtime, so everything under Jobs holds: NATS mode only, one host per module, delivery at-least-once, `max_attempts` retries the whole run, and an undeclared handler fails `Engine.load`.

```python
from naas_abi_core.module.workflows import SyncFlowContext, workflow

class ABIModule(BaseModule):
    @workflow(max_attempts=3, triggers=(Cron("0 0 * * * *", input={"table": "orders"}),))
    def report(self, ctx: SyncFlowContext, inp: ReportInput) -> ReportOutput:
        rows = ctx.step("load", self.load, inp.table)          # journaled: a retry skips it
        ctx.map_call("push", "acme.sink", "push", [{"row": r} for r in rows])
        return ReportOutput(count=len(rows))
```

- **Sync handlers** (`def`) run in a worker thread and get a `SyncFlowContext`: `step`, `map`, `call`, `map_call` and `steps` block while the journal and child runs are handled on the job host's loop. A `step` function runs in the handler's own thread, so the `JobInterrupted` grace behaviour reaches it and a timed-out run keeps its slot until the function returns. `map` runs its items on `concurrency` threads of its own, which `JobInterrupted` does not reach: check `ctx.cancelled` (an `asyncio.Event`: `is_set()`) in long item functions. `payload`, `attempt`, `log`, `skip`, `cancelled` are the `FlowContext`'s.
- **Async handlers** (`async def`) are the SDK's: `ctx` is a `FlowContext` used as is.
- **Step keys must be deterministic** and unique within a run; keys name journal entries (see Decision (2026-10-25) below). A step result is JSON, at most 256 KiB; a run record keeps 64 KiB of output.
- **Declare at runtime** with `declare_workflow(name, handler, input_type=, output_type=, ...)` (sync or async handler), before the module's jobs go to the host (`JobsSealed` afterwards). The engine does this for the bridge below.
- **Calling** (NATS mode, after the host starts; `JobsNotHosted` otherwise). `self.get_workflow(name)` is one of the module's own workflows, typed by its declared input and output. `engine.modules[m].get_workflow(name)` is the same call on another engine module. `self.engine.get_workflow(module_id, name)` reaches any module, engine or remote, by id on the engine's connection; the module must be a declared dependency (a remote one with the `#soft` suffix). `.start(input, idempotency_key=None)` returns a `WorkflowRun` (`status`, `wait`, `result`, `steps`, `cancel`), `.run(input, timeout=)` its output. They are coroutines, awaitable from any loop; from sync code use `asyncio.run(proxy.run(...))`.
- **Inside a workflow**, `ctx.call(module_id, name, input)` and `ctx.map_call(...)` start durable child runs on any replica of any module; a workflow that calls itself is refused (`SelfCall`).

### Workflow/Pipeline bridge

In NATS mode with `nats.workflows.bridge` (default `true`), `Engine` declares each instance in `module.workflows` / `module.pipelines` that has a live typed `run()` (the `process_api.process_parameters_type` predicate, the same one that decides `POST /workflows|/pipelines/<slug>`) as a one-step workflow named `workflow.<slug>` / `pipeline.<slug>` (`process_route_slug`), after `on_initialized` and before the hosts start (`engine_loaders/EngineProcessBridge.py`). The input schema is the parameters model, the description the class's own docstring, `max_attempts=1` (pipelines write to the graph, and a retry would write twice) and `max_concurrency=1` (durable runs of one class never overlap; a REST call or an agent tool can still run the same instance at the same time). The handler validates the input, then runs `run(params)` as the step `run` in the worker thread. Result: made plain JSON the way the REST route sends it (pydantic models, datetimes, paths, decimals, sets, enums; NaN and infinity become `null`, anything else its text), so a result the step journal would refuse never fails a run after `run()` did its work; an rdflib `Graph` → `{"format": "text/turtle", "triples": n, "data": "<turtle>"}`, with `data` replaced by a `note` over 60 KiB; any other result over 60 KiB of JSON → `{"omitted": true, "bytes": n, "limit": n, "note": ...}` (a run record keeps only a truncation marker of larger output; the declared output schema admits the marker). Classes that do not qualify (stub `run`, no parameters model, async `run`, a job of that name already declared) are skipped with a debug log. The classes themselves, their agent tools and the REST routes are untouched. Without NATS, or with the switch off, nothing is declared. Bridged workflows are in `Engine.job_owners` like any job, with their input schema.

## Tools

`module.tools` is the walk #1195 needs (Nexus list and compose). HTTP is narrower: only an `Expose` with a live `as_api` (or a live `run()`) is mounted under `/tools`. A LangChain `BaseTool` is not given REST.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/module/Module_optional_secrets_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/module/ModuleComponentLoader_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/module/ModuleModelLoader_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/module/workflows_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/engine/engine_loaders/EngineProcessBridge_test.py -v
uv run pytest libs/naas-abi-core/naas_abi_core/engine/engine_loaders/EngineWorkflow_integration_test.py -v  # needs nats-server
```

## Decision (2026-10-25): durable workflows for engine modules, and the bridge

**Decision.** Engine modules run the SDK's durable workflows (`naas_abi_sdk.workflows`,
decision in `libs/naas-abi-sdk/AGENTS.md`): async handlers are the SDK's, a sync handler runs
in a worker thread with a `SyncFlowContext` (core's handler wrapper, passed to the SDK's
`declare_workflow(wrap=)` and `method_workflow`, so the descriptor is built in one place).
In NATS mode, with `nats.workflows.bridge` on (the default), `EngineProcessBridge` publishes
every `Workflow`/`Pipeline` instance with a live typed `run()` as a one-step workflow,
`workflow.<slug>` / `pipeline.<slug>`, with the result encoding and output schemas of
`naas_abi_sdk.process_workflows` (the same as a remote module's classes). The classes, their
agent tools and their REST routes do not change.

**Consequences.**
- A bridged class gets limits it never had: `max_concurrency=1` and `max_attempts=1` (a
  pipeline that wrote to the triple store would write twice on a retry). In-process callers
  (agent tools, REST) are not limited, and a REST call and a durable run of one class are not
  serialized against each other.
- A result over 60 KiB does not come back whole: a graph comes without its Turtle (the
  triple count and a note), anything else as the `omitted` marker, and the run still
  succeeds. NaN and infinity are null; a value that cannot be encoded is its text.
- The bridge runs once per engine start, from the instances `on_initialized` built; a class
  that could not be instantiated has no workflow, and a changed parameters model changes the
  input schema on the next start (no schema version).
- `ABI_API_KEY` reaches Nexus' `/api/workflows`: a script holding it can start and cancel
  workflow runs as an operator (audited as `via: api_key`).
- A sync step blocks the handler's thread, not the host's loop, and cannot be interrupted in
  the middle of a blocking C call, as for sync jobs.
- Without NATS nothing is published; the classes keep working in process.


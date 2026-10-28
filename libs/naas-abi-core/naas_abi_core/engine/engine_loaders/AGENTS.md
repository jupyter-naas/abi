# Engine composition loaders

## Purpose
Load configured domain owners and modules, then inject service dependencies.

## Files
- EngineServiceLoader.py: local service owners and transitive requirements.
- EngineNATSLoader.py: endpoints wrapping owners, never the client view.
  `expose_services` applies `nats.max_concurrent_requests` (`nats_dispatch.configure`)
  before it builds the primaries: each service then admits that many calls at once
  (`nats_tracing.ConcurrentRequests`) on as many dispatcher threads.
  `expose_overflow` starts the process's RPC overflow host (`nats_overflow`,
  `nats.rpc_overflow`) once primaries are exposed; shutdown stops it with them.
- EngineNATSDependencies.py: NATS-backed service facades, ordered cache tiers,
  and owned client cleanup.
- EngineModuleLoader.py: core module dependency resolution and lifecycle.
- EngineJobLoader.py: one SDK `JobHost` per module with jobs or workflows, on a
  dedicated loop thread; `SyncJobRunner.py` runs sync handlers in their own thread.
- EngineProcessBridge.py: declares `Workflow`/`Pipeline` instances as one-step
  workflows (below).

## Boundary
Without top-level NATS configuration, keep local references and optional imports.
With NATS, owners and modules receive client views. A service retains its own
persistence adapter but never receives another local owner in `self.services`.
The process-local model registry is available to module bootstrapping only; it
is deliberately absent from cross-domain dependencies.
Do not wire client wrappers to event services when their server-side domain
already emits events. Raw-adapter endpoints (cache/vector/event) have explicit
facade wiring. Only the triple-store owner bootstraps schema state.

Facades wait `nats.client_timeout_seconds` (default 10) for a reply; a route
configured to another engine (`adapter: nats_rpc`) keeps its own `timeout_seconds`.
Long dataset operations pass a deadline per call instead.

A secret fanout may mix local and remote adapters (`[dotenv, nats_rpc]`). The
endpoint serves only the local ones, so the global subject never routes into
itself. The facade reads them through one client to this engine's endpoint,
placed where the first local adapter stood, and keeps the remote ones for
upstream reads.

Kernel jobs (`Engine.job_owners`): dataset maintenance gets the engine's own
dataset service, like its endpoints. Jobs that service adapters offer
(`job_owners(services)`, such as the PostgreSQL event archive) work across
domains, so they receive the facades.

## Workflows

Workflows are jobs with `kind="workflow"`: `EngineJobLoader` hosts them with the
jobs, including those declared at runtime, and a declared one without a handler
fails `Engine.load`. A sync workflow handler (`__abi_sync_flow__`) gets a
`SyncFlowContext` from `SyncJobRunner(context_factory=...)`, built where the host
loop is known, so its `step`/`call` block the worker thread while the host's loop
journals and waits. Each host reads the run records of other modules (a workflow's
children) through `module_documents`, the loader's per-module document namespaces
on the engine's own connection. `EngineJobLoader.workflow(module_id, name)` (and
`Engine.workflow`, `EngineProxy.get_workflow`) returns a `WorkflowProxy` for any
module by id, on that connection and the loader's loop, so a client or CLI engine
that hosts nothing can still start and watch runs. Without NATS or with
`nats.jobs.enabled: false`, workflows are logged as not hosted like jobs.

The bridge (`nats.workflows.bridge`, default `true`) runs in `Engine.load` after
`on_initialized`, in every NATS engine whether it hosts or not (so `job_owners()`
agrees across processes), before `EngineJobLoader.start`. See `module/AGENTS.md`.

## Tests
Run EngineNATSLoader_test.py, EngineNATSDependencies_test.py, and the engine's
optional-NATS/shutdown tests. Jobs and workflows: EngineJobLoader_test.py,
SyncJobRunner_test.py, EngineProcessBridge_test.py, and the broker tests
EngineJobLoader_integration_test.py and EngineWorkflow_integration_test.py
(`nats-server` on PATH). `make demo-sdk` verifies real broker traffic,
cache hot/cold chains, module lifecycle, and worker dependency isolation.

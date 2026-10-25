# Workflows, pipelines, integrations and ontologies in remote modules

## Status
Accepted. The wire contract of calling a process is in
`20261025_remote-module-processes.md`; this record is the decision for the whole
feature and the one to read first.

## Date
2026-10-25

## Context
An in-engine module (`naas_abi_core.module.BaseModule`) offers agents, integrations,
workflows, pipelines, ontologies, apps and jobs. A remote module (`naas-abi-sdk`, over
NATS) offered agents, models, apps and jobs only, and `abi new workflow|pipeline|integration`
refused to run in one. A team that ships a module in its own process had to choose between
its scaling and deployment and the rest of what a module is.

The goal is parity: a remote module authors integrations, workflows, pipelines and
ontologies like an in-engine one, its workflows and pipelines can be called by other
modules and run as jobs, and its ontologies reach the engine's schema graph and the Nexus
ontology catalog. The constraints that already held:

- `naas-abi-sdk` stays independent of `naas-abi-core`, `naas-abi` and the marketplace,
  importable on Python 3.10, with a lazy package `__init__`; pydantic, rdflib and
  LangChain stay behind extras.
- Module identities (20261014_module-identities.md): calls to an instance carry tokens
  bound to it, and a module acts only as itself.
- The discovery registry snapshot stays bounded (20260923_module-discovery-registry.md),
  and replicas of one generation declare identical descriptors.
- In-engine modules keep their behaviour.

## Decision

### Authoring: the same classes, on the SDK
`naas_abi_sdk.workflow`, `.pipeline` and `.integration` mirror the core base classes
(`Workflow[Parameters]`, `Pipeline[Parameters]`, `Integration`), with one difference:
`run` is `async`, since a remote module's services are. A module's `workflows/` and
`pipelines/` folders are scanned like in-engine modules' ones; each class is named by its
class name in snake case (`DigestWorkflow` is `digest_workflow`) and is built after
`on_initialized`, with `New(module)` if it defines one, else an empty configuration. A class
that needs more is bound in `on_initialized` with `expose_workflow` / `expose_pipeline`. The
module's agents use them as LangChain tools (`as_tools()`). Integrations stay a code
pattern: nothing consumes them but the module's own code. `abi new workflow|pipeline|integration`
inside a remote module write SDK scaffolds with a test beside them that imports no core;
only `abi new orchestration` still refuses (a remote module schedules with jobs).

### Calling: a process over NATS
Workflows and pipelines are **processes**. A module lists each in its discovery
descriptor as a `ProcessDescriptor { name, kind, description, contract_major }`
(`ModuleDescriptor.processes = 9`; at most 128, description cut to 512 bytes by the SDK).
The parameters' schema stays in the module: `describe` returns it, so the registry carries
names only.

A call is a unary request/reply on `abi.process.v1`
(`abi.mod.<project>.<instance_id>.process.<kind>.<name>.run` and `.describe`), handled by a
`ProcessHost` in the module and made by `ModuleProxy.get_workflow(name)` /
`get_pipeline(name)` (`run`, `as_tools`, `describe`, `trigger`).

- **Authorization.** Before the module reads the parameters or runs anything it asks
  discovery `authorize_process` with the caller's token. The NATS adapter checks that the
  token is bound to the instance asking; the service checks the lease, that the instance
  declares the process (`PROCESS_NOT_FOUND`) and that it is `READY`
  (`MODULE_UNAVAILABLE`). A caller needs no other grant: the binding is what proves the
  call is meant for that instance, as for agents, models and apps.
- **Deadline.** The caller's deadline is 300 seconds by default and at most 3600. The module
  cancels the run when it passes (`DEADLINE_EXCEEDED`); a run is awaited to the end of its
  cleanup.
- **No retry.** A run is one attempt: it may have completed when a call times out or the
  module stops. A process that matters is idempotent.
- **Large values** travel on the app body streams (an inbox the other side pulls), up to
  256 MiB each way, because the engine's RPC overflow refuses instance-bound tokens.
- A module with workflows or pipelines must run with discovery: `run_module` raises
  before it connects otherwise.

### Jobs: a process with settings
A process class that declares `job = JobSettings(triggers=, timeout=, max_attempts=,
max_concurrency=)` (`naas_abi_sdk.jobs`) is also a job, hosted by the module's existing
`JobHost`: a run record, retries, the System app's job list, and `proxy.trigger(params,
idempotency_key=)` for a manual run. `JobSettings()` alone means manual runs only; no `job`
means no job. Nothing new is registered in discovery: the job is derived, named
`<kind>.<name>` (`workflow.digest_workflow`), and listed with the module's jobs.

- The module declares `get_jobs()` = `jobs` plus the derived ones. It fails at start (before
  it connects) on a name clash with an explicit job and on a `Cron` or `Every` trigger over a
  parameters model with required fields: a scheduled run has the payload `{}`.
- The payload is validated into the parameters model by the host, as for a call; for
  `OnEvent` it is the event's `data`. A payload the model refuses ends the run `FAILED`
  (and is retried up to `max_attempts`): the trigger is not refused, since a trigger only
  writes a message.
- The record's `result` is the workflow's JSON or the pipeline's graph as N-Triples, held to
  64 KiB (`{"truncated": true, "preview": ...}` above it). A caller that needs the whole
  graph calls `run`.
- Delivery stays at least once (module jobs ADR): a run can start again, so `run` must
  tolerate a repeat.

Nexus needed no change: the System app lists the derived job from discovery.

### Ontologies: sent to the schema graph, scoped to the module
A module's `ontologies/**/*.ttl` (except any path with `sandbox`) reaches the engine's
schema graph, as an in-engine module's files do at boot. Remote modules do it over NATS:

- `triple_store.v1.load_schema(source, content_ttl)` is **content-based**, since the engine
  cannot read the module's disk. `source` is `module/<module_id>/<path under ontologies/>`
  and the stored `internal:Schema` has that `filePath` (relative IRIs resolve against
  `http://ontology.naas.ai/<source>`).
- **Scoped to the caller's identity.** A module loads only under `module/<its own id>/`
  (`PERMISSION_DENIED` otherwise); the first-party identities `api`, `engine` and `dagster`
  may load any `module/` source. A malformed source or content that is not Turtle is
  `INVALID_ARGUMENT`, with nothing written. Content may not use the
  `http://triple-store.internal` vocabulary: it would let a module forge another source's
  `internal:Schema`. Module keys cannot assert a first-party identity, so a module never
  loads under another id.
- **READY timing.** `run_module` sends the files once the instance is `READY` or `DEGRADED`:
  never while `STAGED` (a generation behind a live one in a rollout; it sends when it takes
  over), and nothing when it is asked to drain first. A module run without discovery sends at
  start. The send is in the background, retried after 1 s, doubling to 60 s, and never changes
  readiness: a down engine delays the schema, not the module.
- A file the engine already holds writes nothing; a changed one applies the difference.
- A module with ontologies must declare the `triple_store` dependency, checked at start.
- **Additive.** A file a module later removes or renames stays in the schema graph, as it
  does in-engine, where nothing unloads a file either.
- **Nexus.** The ontology catalog lists a remote file by the id `module/<module_id>/<path>`,
  read from the schema graph through the triple store service (cached 30 s, at most 64
  texts), and never opened as a file: a remote id cannot reach the disk. The in-engine
  filters (`owl:Ontology` required, `sandbox` and `processes` skipped) and the workspace
  allowlist (the id, the file name or `<module_id>:<file name>`) apply as before; stats, listings, the dictionary, graphs and export
  resolve both kinds.

### Checked end to end
`scripts/cli_smoke.sh nats` scaffolds a workflow (with job settings), a pipeline, an
integration and a second ontology in a remote module of a new project, runs their tests,
starts the project with `abi dev up`, and checks that discovery lists the processes and the
derived job, that the ontologies are in the schema graph, that another identity's token calls
both processes and one that names an undeclared process is refused, and that the workflow
runs as a job (`scripts/cli_smoke_processes.py`).

## Consequences
- A remote module reaches parity with an in-engine one for the components this record
  covers, and keeps the SDK's rule of no `naas_abi_core` import (a scaffolded test and the
  Docker build check it).
- One call path and one authorization for all the module's components: a token bound to the
  instance, then discovery. A module cannot call a process it was not meant to reach, or
  load an ontology under another module's source.
- The registry grows by names and short descriptions (a derived job adds one entry), so a
  module with the maximum number of processes stays within its share of the snapshot.
- A caller sees a deadline instead of a hung call, but cannot tell a timed-out run from a
  completed one; jobs are the way to run work longer than a caller should wait.
- A removed ontology file lingers until an operator removes it from the triple store;
  `load_schema` has no unload.
- The schema graph is shared and the `module` broker user can still read other modules'
  subjects (20261014_module-identities.md): the scoping stops a module from loading under
  another id, not from reading what the engine serves to everyone.
- The Nexus catalog shows a remote ontology within its cache TTL of a change (or at once
  after the cache is cleared), and shows it only when it is in the schema graph, so a module
  that is down does not hide ontologies it already sent.

## Out of scope
- Kernel REST exposure of remote workflows and pipelines (`/workflows/<slug>`,
  `/pipelines/<slug>` stay in-engine).
- Listing workflows and pipelines in Nexus (their jobs show in the System app).
- In-engine (core) callers of remote workflows and pipelines: `engine.modules[id]` is the
  SDK's.
- Unloading an ontology file a module no longer ships.
- Dagster orchestrations: jobs replace them (`abi new orchestration` still refuses in a
  remote module).

# Workflows and pipelines served by remote modules over NATS

## Status
Accepted.

## Date
2026-10-25

## Context
In-engine modules hold workflows and pipelines (`Expose` subclasses) that their
agents use as tools and the kernel REST API mounts. Remote modules (`naas-abi-sdk`)
can now write the same classes (`naas_abi_sdk.workflow`, `.pipeline`), but they run
only inside their own process: another remote module cannot call them.

Requirements:

- A module calls another's workflow or pipeline with `engine.modules[id]`, directly
  and as agent tools, the way it already calls its agents and models.
- A caller is authenticated like every call to a module: its token is bound to the
  instance it calls (docs/adr/20261014_module-identities.md), and the process must be
  one the instance declares, before the module reads anything or runs anything.
- The discovery registry stays one bounded snapshot (20260923_module-discovery-registry.md):
  parameter schemas cannot be registered.
- Parameters and results can be large (a graph, a document), above one NATS message.
- A run can take minutes, so it cannot ride the 10 second RPC timeout.

## Decision
**A process is a unary, instance-addressed request/reply on the module's own
subjects, with a deadline.** It follows the model and app hosts.

### Discovery
`ModuleDescriptor.processes = 9` lists `ProcessDescriptor { name, kind, description,
contract_major }`. `kind` is `workflow` or `pipeline`; a name is a subject token of at
most 64 characters, unique per kind. At most 128 per module, a description of at most
4 KiB (the SDK sends the class docstring cut to 512 UTF-8 bytes, on a character
boundary, so 128 descriptors always fit) and 128 KiB in all. A refused registration names
the limit it hit (count, name, kind, description, duplicate or total size).
Replicas of one generation declare identical processes.

`authorize_process` (`AuthorizeProcessRequest`/`Response`) is `authorize_model` for
processes: the provider sends its instance id, lease token, the process kind and name
and the caller's token. The NATS adapter verifies that token is bound to the instance
asking; the service checks the lease and owner, the declaration (`PROCESS_NOT_FOUND`)
and that the instance is READY (`MODULE_UNAVAILABLE`). Like `authorize_app`, a recent
snapshot that already allows the call answers it; a refusal always reads the registry.

### The call
`abi.process.v1` (`naas_abi_proto/process/v1/process.proto`) on
`abi.mod.<project>.<instance_id>.process.<kind>.<name>.run` and `.describe`.

- `RunRequest { context, name, parameters_json, deadline_seconds }` answers
  `RunResponse { error, result_json, graph_nt }`: JSON for a workflow, N-Triples for a
  pipeline's rdflib `Graph`. `DescribeRequest`/`DescribeResponse` give the parameters'
  JSON schema and the full description; the schema stays in the module.
- The module authorizes the caller (an answer is reused for at most 5 seconds, never
  past the token's `exp`, and a refusal is never kept), validates the parameters into
  the process's pydantic model (`INVALID_ARGUMENT`, naming fields and no values), runs
  it for the caller's deadline (300 seconds by default, at most 3600 like an agent run: a
  longer one would pin a call slot and a drain; `INVALID_ARGUMENT` above it) and cancels it
  when it passes (`DEADLINE_EXCEEDED`). A `CancelledError` the process raises itself is
  its failure (`PROCESS_ERROR`), not a cancelled call. A run is awaited to the end of its
  cleanup when it is cancelled, by the deadline or by `close()`. A failing process answers `PROCESS_ERROR` without its
  exception text. Runs go side by side up to `max_concurrency` (64), like the other
  hosts; describing is apart.
- **A run is never retried**, by the proxy or anything else: it may have run when a call
  times out or the module stops. A run cut off by a stopping module tells its caller
  (`CANCELLED`).
- **Large payloads** use the app body streams (`BodySource`, `pull_body`: one chunk per
  pull, `abi.app.v1` `BodyPull`/`BodyChunk`), not RPC overflow
  (20261003_nats-rpc-overflow.md). Overflow parks and fetches through the engine's
  `abi.rpc.overflow` host, which refuses a token bound to an instance and which modules
  may not subscribe to. Parameters above one message (about 250 KiB, less on a small
  broker) go in `parameters_inbox` (the caller holds them, the module pulls them after it
  authorized the call), a result in `body_inbox`; at most 256 MiB each way. An inbox a
  peer names must be an `_INBOX` subject. A result stream keeps its call slot until the
  reader has pulled it all (a drain waits for it), so a reader that stops pulling for 20
  seconds is dropped, and the slot with it. A schema too large for one message is
  answered `PAYLOAD_TOO_LARGE` by `describe`.
- **Shutdown.** The host joins `run_module`'s drain: on SIGTERM it stops taking calls,
  finishes the runs in progress (up to the drain timeout), and the module then
  unregisters. It is closed after the app host.

### Callers
`ModuleProxy.get_workflow(name)` and `get_pipeline(name)` return a `ProcessProxy` at
once; it is awaitable (`await proxy` describes it and keeps the schema). `describe()`,
`await run(params, *, timeout=None)` (a dict or pydantic model; a pipeline returns a
`Graph`) and `as_tools()` (a LangChain tool whose arguments are the schema, run on the
module's loop; needs the awaited proxy). `Transport.call` takes a per-call `timeout`
so a run is not bound to the transport's. Errors: `PROCESS_NOT_FOUND`,
`MODULE_UNAVAILABLE`, `INVALID_ARGUMENT`, `DEADLINE_EXCEEDED`, `PROCESS_ERROR`.

A module that has workflows or pipelines must run with discovery: `run_module` raises
before it connects otherwise.

## Consequences
- Another module's workflow is one `await` away, and an agent can use it as a tool;
  discovery refuses a caller whose token is not bound to the instance, and an
  undeclared process, before the handler runs.
- The registry carries names and short descriptions only, so a module with the
  maximum number of processes stays within its share of the snapshot.
- A caller sees a deadline, not a hung call, and the module stops the work. A timeout
  can still hide a completed run, so a process that matters must be idempotent.
- Large values are held whole in memory on both ends, as with overflow; the body
  streams bound the chunks, not the values.
- A body inbox is a random `_INBOX_MODULES` subject known to the two parties; modules
  can still see each other's subjects on the shared `module` broker user
  (20261014_module-identities.md), as with app bodies.
- Out of scope here: calls from in-engine modules, kernel REST exposure, listing
  processes in Nexus. Each can be added on the same descriptor and subjects.

## Amendment (2026-10-25): jobs and ontologies
Running a process as a job (`job = JobSettings(...)`, `ProcessProxy.trigger`) and the
remote ontologies are decided in
`20261025_remote-module-workflows-pipelines-ontologies.md`, which also records the
whole feature and what stays out of scope. A derived job adds no descriptor field: it is
listed with the module's jobs, named `<kind>.<name>`.

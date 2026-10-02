# Standalone package

Keep this package independent of naas-abi-core, naas-abi, and marketplace.
Transport DTOs are protobuf messages. Public service facades expose Python values
and generated SDK dataclasses, never engine domain objects. See services/AGENTS.md.
Generated artifacts are checked in; regenerate with `make generate` in the proto package.
Use UV. `make deps`, `make test`, `make lint`, and `make build` are the local gates.
Tests live under tests/. Update the standalone module demonstration when adding endpoints.

LangGraph support lives in langgraph.py and is opt-in via [langgraph]; never import
it from package __init__ or make it a base dependency. Only async graph execution
is supported. Keep checkpoint schema versions and pending-write semantics explicit.
Document module namespaces are a programming boundary, not authorization.
The document schema is in langgraph_documents.py, shared with core's synchronous
engine saver and the Nexus viewer: collections, ids, write plans (schema 2 stores
increments: content-addressed blobs, list elements and chunks, parts above
256 KiB), byte-bounded read batches, decoding, and schema 1 reads. Savers only do
I/O. Stored documents depend on it, so change it only with a schema version.
Keep it core-free and importable on Python 3.10; tests/test_langgraph_documents.py
pins the ids. Never deserialize in the pure read helpers (the viewer relies on it).


AgentProxy and AgentHost use document CAS for durable invocations and non-expiring
conversation claims. Never infer execution ownership from discovery leases or
replay an orphaned run. Core Agent/IntentAgent compatibility belongs in core's
RemoteAgentAdapter; only agent_tools imports optional LangChain dependencies.
Agent streaming preserves string event/data pairs and sequence-based replay.

Model proxies/codec import optional LangChain through [models]. Never import them
from package __init__ or the base service catalog. Registry facades lazy-load
proxies on model lookup. ModelConnection keeps NATS I/O on the resolving loop;
sync callers must use another thread. Stream IDs are caller-bound, ephemeral,
sequence-checked handles; never retry inference or cursor reads automatically.

`transfer.py` owns shared chunk framing and session cleanup. Object facades stream
bounded reads; model proxies assemble logical protobuf frames. Preserve owner-loop
execution, sequence checks, caller binding and no automatic replay. Per-exchange
RPC timeouts must not impose a total model-generation deadline.

Agent output format 2 stores immutable document fragments and manifests before
publishing the run sequence cursor. Never truncate events or retry uncertain
writes. Preserve caller authorization on fragment reads and output-format
negotiation. Membership caches are bounded to one second, not a lease interval.

`agents/` (extra `[agent]`) is the core Agent/IntentAgent behaviour, async and
core-free: same graph node names, prompts, callbacks, hooks and stream_invoke
events. `_messages.py` and `intents.py` are copied from naas_abi_core on purpose;
change them together. tests/agent_parity at the repository root runs every
scenario against both runtimes: extend it before changing either agent. Host an
agent with `expose_agent(name, agent.as_handler())` and checkpoint it with
`document_memory(engine.services.document, agent_memory_id(module_id, name))`.
v1 has no local sub-agents; remote agents (AgentProxy) are passed as tools.

Jobs (`jobs.py`, `job_host.py`, ADR docs/adr/20261001_nats-jobs.md) replace Dagster
schedules. Declare `JobDescriptor`s in `jobs` or use `@job` on async methods; bind
others with `expose_job`. `JobsMixin` is shared with core modules (sync handlers
allowed there): keep `jobs.py` importable without `nats` (stdlib and proto only),
and keep the package `__init__` lazy for the same reason. Triggers are JetStream message schedules (`Cron`, `Every`,
NATS >= 2.14) and core-NATS events (`OnEvent`, at-most-once bridge). Delivery is
at-least-once: handlers must be idempotent. One durable pull consumer per job;
`max_concurrency` is `max_ack_pending`, retries are `nak(delay)`. Run records live
in the provider's document namespace (`job_runs_<hash(project)>`), written with CAS.
Cancellation is cooperative (`ctx.cancelled`). tests/test_jobs_integration.py needs
`nats-server` on PATH; run it after touching schedules, consumers or acks.

`telemetry.py` is the one OpenTelemetry implementation (core reuses it): W3C trace
context in NATS headers, CLIENT spans in `Transport.call`, CONSUMER spans for job
runs, spans for agent submits and runs, `record_error` on error replies, and the
owner's SERVER span per transfer session (`serve_transfer`: open to close, expiry
or stop; current only around the handler). Keep it stdlib plus optional
OpenTelemetry API, and a no-op without a provider. Modules
export spans when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (`[otel]` extra). See
docs/adr/20261002_observability.md.

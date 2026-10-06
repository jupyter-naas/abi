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
It also holds retention (`kept_checkpoints`, `RetentionReport`; the savers'
`prune`/`aprune` do the I/O) and secret redaction (`RedactingSerializer`: a
`SecretStr`/`SecretBytes` is stored as one holding `REDACTED_SECRET`, never in
clear). Redaction does not change the document layout.


AgentProxy and AgentHost use document CAS for durable invocations. A conversation
claim is released when its owner instance is absent from a successful discovery
lookup, so that thread can accept a new run. The orphaned invocation is marked
failed and is not replayed. A failed lookup keeps the claim. This process never
treats its own instance as absent. A lost lease (expiry or eviction) registers
the same instance id again with a fresh lease token, so run owners, claims and
agent and model subjects stay valid; `AgentHost._bind` keeps its subscriptions
when the id did not change. A provider process accepts at most 200 live
runs, shared by every agent it hosts. `invoke` and `stream_invoke` send a 300
second deadline unless the caller passes `timeout`; `deadline_seconds` 0 on
submit still means no deadline. The 300 second idle watchdog cancels a streamed
run with no new event, and any run without a deadline. An unstreamed run (invoke
mode, or a handler without `stream_invoke`) reports nothing until it returns, so
its deadline alone bounds it. Core Agent/IntentAgent compatibility belongs in core's
RemoteAgentAdapter; only agent_tools imports optional LangChain dependencies.
Agent streaming preserves string event/data pairs and sequence-based replay.

A rollout id (`DiscoveryConfiguration.rollout_id`, or `ABI_ROLLOUT_ID`) marks
processes that cut over together. `rollout_modules` (or `ABI_ROLLOUT_MODULES`,
comma-separated) names every module id that must be initialized first. Empty
means this module alone. Discovery keeps the previous generation `READY` until
that set is up, then marks it `DRAINING` and serves the new one. `STAGED` is a
new generation waiting behind a live one. A rollout may add or change agents,
jobs and models without a contract bump; replicas of one rollout must match.
Job schedules and consumers are module-wide, so with a rollout id `run_module`
starts the job host only once discovery reports the instance `READY` or
`DEGRADED`, never while `STAGED`. Before it can serve, it creates the missing
job consumers (`JobHost.prepare`: no fetch, no schedule, no change to an
existing consumer), so a trigger for a new job sent after the cutover waits
for the host. `SIGTERM` and `SIGINT` drain the
process: new agent submits, job fetches and model chats stop, accepted runs and
jobs finish, then the process unregisters. A live run keeps its claim until it
finishes. See the discovery ADR, section "Rollouts and draining (2026-10-05)".

`ABI_HEALTH_PORT` (or `run_module(..., health_port=)`) opens a standard-library
HTTP probe on `ABI_HEALTH_HOST` (default `0.0.0.0`). Unset means no port.
`GET /health` is liveness and stays 200 while the process is up, including
`DRAINING` and `STAGED`. `GET /ready` is 200 for `READY`, and for `DISABLED`
when discovery is off. Every other status is 503. The server closes when the
module exits.

A module can serve a chat model (`ModelDescriptor`, `expose_model`, `ModelHost`).
Another module calls `engine.modules[id].get_chat_model(name)`. The call is unary,
instance-addressed, and authorized with `authorize_model`. The handler returns
text or an `AIMessage` with tool calls. The caller's agent executes the tools.
Streaming is refused. Engine model registration stays
on the model registry.

Model proxies/codec import optional LangChain through [models]. Never import them
from package __init__ or the base service catalog. Registry facades lazy-load
proxies on model lookup. ModelConnection keeps NATS I/O on the resolving loop;
sync callers must use another thread. Stream IDs are caller-bound, ephemeral,
sequence-checked handles; never retry inference or cursor reads automatically.

`messages.py` sizes messages as the broker does (body and header block) and
`reply()` answers without echoing the request's headers; use it instead of
`Msg.respond`. `claim_check.py` carries published, queued and job-trigger
messages above the broker limit through a JetStream object store
(docs/adr/20261003_nats-claim-check.md); `BusClient` subscriptions resolve them
in place. Every raw NATS send is listed in core's
`engine/nats_send_sites_test.py`: a new one must go through these helpers.
`overflow.py` is the client side of RPC overflow (payloads above the broker
limit as transfer/v1 frames, docs/adr/20261003_nats-rpc-overflow.md), used by
`Transport` and core's `NatsRPCClient`. A call says `Abi-Overflow: 1` before an
engine may park its reply; never drop that header or download without the
announced size. `transfer.py` owns shared chunk framing and session cleanup. Object facades stream
bounded reads; model proxies assemble logical protobuf frames. Preserve owner-loop
execution, sequence checks, caller binding and no automatic replay. Per-exchange
RPC timeouts must not impose a total model-generation deadline.

Agent output format 2 stores immutable document fragments and manifests before
publishing the run sequence cursor. Never truncate events or retry uncertain
writes. Preserve caller authorization on fragment reads and output-format
negotiation. Membership caches are bounded to one second, not a lease interval.
`AgentHost` reuses discovery's authorization of a (caller token, agent) for
status, event and cancel for `AUTHORIZATION_SECONDS` (5 s), never past the
token's `exp`, and never caches a refusal. A submit always asks discovery.

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
`max_concurrency` is `max_ack_pending`, retries are `nak(delay)`. Attempts are
handler starts counted on the run record (`max_deliver` is unlimited): a delivery
that can't read or record its run is nak'ed with backoff and uses none. Publish a
schedule only when missing or changed, with `Nats-Expected-Last-Subject-Sequence`:
replacing one restarts an `@every` interval. A run ID belongs to a delivery only
when `fired_at` matches (a recreated stream reuses sequences). A retry its
trigger's `Nats-TTL` would not outlive fails the run instead.
Renew acknowledgement independently of log persistence; supervise renewal failure.
Save completion before ack/term/nak and retire redelivered terminal records without
executing handlers again. An unsaved completion keeps its delivery and its slot
until the store recovers (on purpose; logged as an error after 60 s). Event deduplication requires a source Nats-Msg-Id and
includes the target module/job; manual idempotency keys are target-scoped too.
Run records live in the provider's document namespace (`job_runs_<hash(project)>`), written with CAS.
Cancellation is cooperative (`ctx.cancelled`). tests/test_jobs_integration.py needs
`nats-server` on PATH; run it after touching schedules, consumers or acks.
A module triggers its own jobs through its bound host (`trigger_job` for sync
code, `atrigger_job` for async; `JobsNotHosted` outside a running host), with an
optional `idempotency_key` (`Nats-Msg-Id` dedup). `ctx.skip(reason)` records a
run as SKIPPED; hosts prune finished runs (`JobRetention`: skipped after 1 h,
others after 7 days, 1,000 per job) and fail runs lost with a crashed host
(`reap_lost_runs`: RUNNING on the last attempt, no heartbeat for 5 min; or
RUNNING/RETRYING with attempts left whose trigger left the stream).
`OnEvent(filter=...)` drops events before a
trigger is published; `event_filter.py` mirrors core's `EventFilter.matches`,
change them together.

`telemetry.py` is the one OpenTelemetry implementation (core reuses it): W3C trace
context in NATS headers, CLIENT spans in `Transport.call`, CONSUMER spans for job
runs, spans for agent submits and runs, `record_error` on error replies, and the
owner's SERVER span per transfer session (`serve_transfer`: open to close, expiry
or stop; current only around the handler). Keep it stdlib plus optional
OpenTelemetry API, and a no-op without a provider. Modules
export spans when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (`[otel]` extra). See
docs/adr/20261002_observability.md.

Test layout is a deliberate exception to the monorepo rule of a `_test.py` beside
each file: SDK tests live in `tests/test_<module>.py`, outside the published
package, and the CI `packages` job runs them alone on Python 3.10 to 3.12. Add a
module's tests to its `tests/test_<module>.py`. `tests/conftest.py` fails a test
skipped for want of `nats-server` when `ABI_REQUIRE_NATS_SERVER=1` (set in CI);
it mirrors core's `engine/nats_test_server.py` hook, so change them together.

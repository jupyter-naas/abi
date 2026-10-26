# Standalone package

Keep this package independent of naas-abi-core, naas-abi, and marketplace.
Transport DTOs are protobuf messages. Public service facades expose Python values
and generated SDK dataclasses, never engine domain objects. See services/AGENTS.md.
Generated artifacts are checked in; regenerate with `make generate` in the proto package.
Use UV. `make deps`, `make test`, `make lint`, and `make build` are the local gates.
Tests live under tests/. Update the standalone module demonstration when adding endpoints.
After subscribing (or publishing) and before saying so, `await flush_to_broker(nc)` (`broker_flush.py`), never `nc.flush()`:
nats-py's PING overtakes the buffered SUBs, so a request right after could find no responder. Core re-uses it.

LangGraph support lives in langgraph.py and is opt-in via [langgraph]; never import
it from package __init__ or make it a base dependency. Only async graph execution
is supported. Keep checkpoint schema versions and pending-write semantics explicit.
Document module namespaces are a programming boundary, not authorization.
Identity, credentials and the permission manifest: see "Identity, credentials and
permissions" at the end of this file.
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
runs, shared by every agent it hosts. `AgentHost` and `ModelHost` answer their
calls side by side, up to `max_concurrency` (64) at once (`concurrency.py`,
`ConcurrentCalls`, shared with core's kernel services and discovery): a
handler awaited in a subscription callback would answer one call at a time.
`AgentHost.close()` answers the calls received before it cancels runs;
`ModelHost.close()` cancels the chats still running. `invoke` and `stream_invoke` send a 300
second deadline unless the caller passes `timeout`; `deadline_seconds` 0 on
submit still means no deadline. The 300 second idle watchdog cancels a streamed
run with no new event, and any run without a deadline. An unstreamed run (invoke
mode, or a handler without `stream_invoke`) reports nothing until it returns, so
its deadline alone bounds it. Core Agent/IntentAgent compatibility belongs in core's
RemoteAgentAdapter; only agent_tools imports optional LangChain dependencies.
Agent streaming preserves string event/data pairs, a tool response's `chat_source: False`
opt-out, and sequence-based replay.

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
process: new agent submits, job fetches, model chats and app requests stop,
accepted runs, jobs and app requests finish, then the process unregisters. A
streamed app response may finish too, unless it is server-sent events or idle
for a second: those end with an error, and their readers reconnect elsewhere. A live run keeps its claim until it
finishes. Discovery's side of rollouts: core's `services/discovery/AGENTS.md`, "Generations".

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
messages above the broker limit through the stream `ABI_CLAIM_CHECKS`, under
the scope of their topic or job (chunks under a SHA-256 in the reference);
`BusClient` subscriptions resolve them in place. Behind the broker's auth
callout a module creates no stream or consumer and writes nothing into the
jobs stream: `broker_control.py` asks the engine (`abi.broker.v1.<operation>`)
to create them, to store its triggers, schedules and cancels (sealed by the
engine: the job host takes no unsealed one, `verify_trigger`) and to read
claim checks (`claim_check.ThroughEngine`), and falls back to doing it itself
when no engine answers. Every responder answers only
`_INBOX.` reply subjects (`messages.reply_allowed`). Every raw NATS send is listed in core's
`engine/nats_send_sites_test.py`: a new one must go through these helpers.
`overflow.py` is the client side of RPC overflow (payloads above the broker
limit as transfer/v1 frames), used by
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

Jobs (`jobs.py`, `job_host.py`) replace Dagster
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

`lifeline.py` stops a process whose NATS connection closed for good (nats-py
gave up reconnecting), so its supervisor restarts it. Every long-lived connection passes a
`Lifeline`'s `closed` as `closed_cb` and closes on purpose through
`Lifeline.close(nc)`: `Transport` here, and in core the shared engine
connection, the lease and the bus. `run_module` opts in for its run
(`stopping_on_loss`), core's `api()` in NATS mode without reload; otherwise a
loss is only logged. Stopping is SIGTERM, then `os._exit(1)` after
`HARD_EXIT_SECONDS` (20). Opting in is process-wide: tests pass their own `stop`.

`telemetry.py` is the one OpenTelemetry implementation (core reuses it): W3C trace
context in NATS headers, CLIENT spans in `Transport.call`, CONSUMER spans for job
runs, spans for agent submits and runs, `record_error` on error replies, and the
owner's SERVER span per transfer session (`serve_transfer`: open to close, expiry
or stop; current only around the handler). Keep it stdlib plus optional
OpenTelemetry API, and a no-op without a provider. Modules
export spans when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (`[otel]` extra).

## Identity, credentials and permissions

The engine side (policy language, evaluation, token issue and exchange, service
accounts, broker permissions, approval) is core's `services/iam/AGENTS.md`; this is
what the SDK does with it. The SDK holds no signing key and no crypto library:
it carries credentials the engine issued and never verifies one itself (a trigger's
seal is checked by asking the engine, `broker_control.py`).

### A module's credential (`credentials.py`)

- **`ABI_SERVICE_KEY`** is the module's service key, `abi_sk_<key id>_<secret>`
  (`ServiceKey`: a 16 character key id, then the secret). It replaces the old shared
  `NATS_JWT_SECRET` and `ABI_SERVICE_TOKEN`; a module can no longer sign a token as
  `api`, `engine` or another module. `module_runner.py` reads it, `Transport` accepts
  a key or a `ServiceKey` as its `token`, and `run_module(token=...)` passes it on.
  A process of the engine passes bare tokens (a string or a callable) instead.
- **The key does two things.** It logs in to the broker (user `sa`, the key as
  password, inbox prefix `_INBOX.<key id>`, which only this key's connections can
  read), and the broker's auth callout gives the connection the subjects its
  approved policy allows. It is also exchanged at `abi.iam.v1.token` for an access
  token of the audience `abi:nats` (ten minutes at most, exchanged again at half its
  life; an expired token is kept while the engine cannot be reached). Every call
  carries it in `Nats-Auth-Token`.
- **Host tokens.** A call to a module host (subjects `abi.agent.<project>.<sa>...`
  and `abi.mod.<project>.<sa>...`, `transport.host_recipient`) never carries the
  module's `abi:nats` token: the host reads every token it serves and `api`'s would
  be good everywhere. The key buys one token per host, audience `abi:host:<sa>`
  (`host_audience`, cached per audience, at most 256), which the kernel services
  refuse and discovery accepts only from that host. A transport given bare tokens
  takes a `host_token` (a token, or a function of `<sa>`) and raises
  `NoHostTokenError` rather than call a host without one.
- **Renewing the connection.** The broker expires a callout user in five minutes
  (ten at most) and nats-py closes an expired connection instead of reconnecting
  it, so a transport logged in with a key reconnects itself every 120 seconds
  (`renew_seconds`): the callout then computes the subjects again from the policy as
  it is. A call in flight during the few milliseconds of a renewal is lost, as in any
  reconnect; a call starting then waits for it. `Transport.reconnect()` is the
  same on demand (after an approval). Revoking a key ends the next exchange and
  the next connection; tokens already issued expire within ten minutes.
- **No broker permission to create anything.** Behind the callout a module cannot
  create a stream or a consumer nor write the jobs stream, and replies only on
  `_INBOX.` subjects; see `broker_control.py` for the operations the engine does for it
  (`abi.broker.v1.<operation>`).
- **Local key.** `abi dev up`, `abi deploy` and `abi iam service-account create`
  make the account `module/<project>/<module_id>` and its key
  (`abi iam key create|rotate|revoke`); `module_account(name)` splits the name.

### The permission manifest (`permissions.py`, `module._await_approval`)

A module asks for what it needs as a policy document (the language of core's
`services/iam/AGENTS.md`):

1. `BaseModule.permissions` (a dict), else
2. `permissions.yaml` beside the module's code (JSON also reads without PyYAML), else
3. a default derived from `ModuleDependencies` (`default_manifest`): `document` is the
   module's own namespace (`${module.id}`); `secret` the names `<module id>/...`;
   `dataset` the namespace `default` and the catalog, with `dataset:QueryUnchecked`
   denied; `email` sending only (the platform keeps a copy of what is sent, sign-in
   codes included, so reading it is named in a manifest); `source_control` all but
   `AddCollaborator`; any other declared service every action of it; the dependency
   modules' agents, models and apps (never the identity provider's `admin` app) and
   the runs the module starts, for it and for the user it acts for; its own jobs, each
   by name. `bus` has no default: a module using it declares `bus:*` on
   `abi:-:-:bus:topic/<topic>`. Default grants contain no admin action.

`${module.id}` and `${module.project}` are bound when the manifest is approved.

At start, `run_module` calls `_await_approval` before anything else (an unapproved
module can call nothing but IAM):

- It applies to a service key of a module account only (`module/<project>/<module_id>`);
  a script's or CI account, or a process of the engine, skips it. The module id must
  equal the key's, else the start fails.
- It submits the manifest (`abi.iam.v1.submit_manifest`; `iam:SubmitManifest` is in the
  module's bootstrap policy) and asks again every five seconds, logging the command
  an administrator runs (`abi iam module approve <account>`). `rejected` fails the
  start with the reason. An unapproved module is not in discovery.
- When a manifest changes, the new one is pending and the previous approved one stays
  in force: the module starts on it and logs a warning.
- When the approval lands after the connection opened (or on submission, in
  `abi dev up`, which approves automatically), the transport reconnects so the broker
  grants the new subjects.

### Tokens the SDK meets

Engine tokens are ES256 JWTs with one audience and at most ten minutes of life. An
SDK module deals with three audiences: `abi:nats` (its own, for the kernel services),
`abi:host:<sa>` (above) and `abi:delegated:agent` (below). `sub` is the principal;
`act.sub` the actor when someone acts for `sub`. `AgentHost` reads `aud`, `sub` and
`act` of a delegation without verifying (the engine does at every use); the others
(`abi:session`, `abi:delegated:{app,preview,coding,api-key}`) never reach a module
host.

### CallContext (`call_context.py`)

One ContextVar, `CallContext`, holds the caller of the call being served: `principal`
(the actor), `on_behalf_of` (the user, when acting for one), `audience`, `token_id`,
`token_issued_at`, `scope` (the token's `abi_scope`), `workspace_id` (the target
workspace of a create: a request input, not identity), `trace_id`, `triggered_via` and
`delegated_token`. `CallContext.user` is `on_behalf_of`, else the principal when it is a
user: services use it wherever an operation concerns "the user". The default is
`ANONYMOUS`, which every check denies.

- Core's `engine/call_context.py` re-exports it, so the engine and the SDK clients it
  runs read one value; `engine/call_context_types.py` is a verbatim copy for installs
  without the SDK (`nats` extra), so keep them equal (a test checks it).
- It is set only from verified credentials: a NATS request's `Nats-Auth-Token`, a Nexus
  session, or inheritance. Never from request fields: `principal_id` and `tenant_id`
  of the proto `CallContext` are reserved and ignored, and `user_id` fields and `X-User-*`
  headers are not identity. A module learns who calls only from the delegation's
  verified claims: credentials never reach module code (Nexus forwards to a remote app
  only content-negotiation, conditional and range headers, `User-Agent` and `x-*` headers
  but `x-forwarded-*`, `x-real-ip` and `x-api-key`; never `Authorization`, and of the
  browser's cookies only the app's own, which it set itself, never the Nexus session).
- Tasks and `asyncio.to_thread` copy it; a raw thread or executor submission needs
  `contextvars.copy_context().run`.
- Helpers: `use_call_context(ctx)`, `current_call_context()`, `set_call_context` /
  `reset_call_context` (for code that cannot wrap a block), `service_account(name)`,
  `user(id)`. `as_service_account` is core's, in process only; remote code has no
  equivalent: it holds only its token.
- `Transport.call` puts the call's trace and workspace in the request's `context`.

### Acting for a user (delegation)

The user a call acts for travels in an `abi:delegated:agent` token (`sub` the user,
`act` the acting service), never in a header: the kernel refuses `Abi-On-Behalf-Of`
(`on-behalf-of refused: ...`).

- A transport of `api` or `engine` is built with `delegate(user, recipient, scope)`,
  which returns the token for the user the call acts for (for a call to a module host,
  one naming that module as the actor, so the host holds a token good for that
  module for that user and nowhere else). Without a delegate a transport calls as
  itself; with one that fails, the call fails: it never calls as the transport alone,
  which would drop the user.
- A module host runs an invocation with the delegation it was handed
  (`SubmitRequest.delegated_token`, kept only if it names the run's owner and this
  host's own account as the actor: `agent_host.py`, otherwise the run is the module's
  own): `CallContext.delegated_token`. `Transport.delegated_token` sends it, in place
  of the module's token, on the kernel calls the run makes for that user, and renews
  it through the service key (`ServiceKey.renew_delegation`: IAM exchanges it again
  for the same audience, up to eight hours after it began). A module's own side of the
  check is `builtin.module_bootstrap` (`OwnHosted`, `OwnRuns`).
- A scope (`abi_scope`) travels with every delegation, so a personal key reaches no
  further over NATS than in process.
- `engine.services.iam` (`services/iam.py`) needs no dependency declaration: IAM
  answers for the module's own verified identity and authorizes its own operations
  (`abi.iam.v1.*`).

The claims `AgentHost` reads from a delegation itself are unverified and only decide
which delegation it keeps; the engine verifies the token at every kernel call.

## Tests

Test layout is a deliberate exception to the monorepo rule of a `_test.py` beside
each file: SDK tests live in `tests/test_<module>.py`, outside the published
package, and the CI `packages` job runs them alone on Python 3.10 to 3.12. Add a
module's tests to its `tests/test_<module>.py`. `tests/conftest.py` fails a test
skipped for want of `nats-server` when `ABI_REQUIRE_NATS_SERVER=1` (set in CI);
it mirrors core's `engine/nats_test_server.py` hook, so change them together.
Identity is covered by `tests/test_credentials.py` (key, exchange, host tokens),
`test_permissions.py` (the manifest and its defaults), `test_call_context.py`,
`test_transport.py` (delegation, host tokens, reconnects) and `test_agent_host.py`
(the delegation a run executes with).

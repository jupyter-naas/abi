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

Ontologies (`ontologies.py`): a module sends the `.ttl` files of `ontologies/` (next to
its package, found like `apps/`) to the engine's schema graph with
`engine.services.triple_store.load_schema(source, content)` (the endpoint's rules are in
core's `services/triple_store/AGENTS.md`). `BaseModule.ontologies` is `None` (discover
`ontologies/**/*.ttl`, skipping a path under `ontologies/` with `sandbox` in it, any
case), a tuple of files relative to `ontologies/`, or `()`. Each is sent as
`module/<module_id>/<path relative to ontologies/>`; `schema_source` checks the names
the engine would refuse, and `run_module` raises before it connects, also when a module
has ontologies but does not declare `triple_store`. The engine loads a source for a caller
holding `triple_store:LoadSchema` on `schema/<source>`: the default manifest asks for the
module's own (`OwnOntologies`, `schema/module/${module.id}/*`). `OntologyLoader` runs as a background
task once the instance is `READY` or `DEGRADED` (never `STAGED`, and not at all when it is
asked to drain first; a module without discovery sends at start). A failed load is logged
at error level (`naas_abi_sdk.ontologies`) and retried, after 1 s and doubling to 60 s,
reading the file again each time; it never changes readiness or ends the module. A
refusal no retry changes (`TERMINAL_CODES`: `INVALID_ARGUMENT`, `PERMISSION_DENIED`, `NOT_FOUND`) is
logged once, the file moves to `OntologyLoader.refused` and is not sent again until the
process restarts.
A timeout can hide a completed load: the retry reports no change. Loading is
additive: a file removed later stays in the schema graph, and nothing here unloads it.
Keep `MAX_SOURCE_LENGTH` and the name rules equal to core's `parse_schema_source`.

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

Who a run runs as: every attempt of a manual trigger is authorized
(`discovery_job_authorizer`, `discovery:TriggerJob`), and the authorizer returns the
context the run executes in. A trigger Nexus or the engine stored for a user carries the
engine's delegation (`DELEGATION_HEADER`, sealed): the run is the module acting for that
user (`call_context.delegation_context`, as an agent run). The handler and its steps'
functions run under it, so their kernel calls carry the delegation, renewed through the
module's key up to 8 hours after the trigger. The run's bookkeeping stays the module's own
(`FlowContext.host_context`): its journal and results, the triggers, records and cancels of
its child runs (a module hands no user to another). Without a delegation (a module's
trigger, a schedule, an event) the run is the module's own.

Workflows (`workflows.py`, Decision (2026-10-25) below) are jobs
with `kind="workflow"`, JSON Schemas on the descriptor and a step journal. Same rules
as jobs.py: stdlib and proto only at import (nats and `services.errors` load lazily),
no pydantic import (models are duck-typed: `model_json_schema`, `model_validate`,
`model_dump`). `@workflow` methods are `(self, ctx: FlowContext, inp) -> out`;
`declare_job`/`declare_workflow` add jobs at runtime (instance level, before the host
starts; `run_module` takes the descriptor after `on_load`). Descriptors are bounded
(schema 16 KiB, trigger input 4 KiB, whole 64 KiB: `jobs.py` enforces it). The journal is
`workflow_steps_<h>` (summaries, no results) and `workflow_results_<h>` (JSON text) in
the module namespace, ids `<run id>#<step key>`, results written before the summary,
`fired_at` guarding recreated streams; `job_host.prune` deletes it with its run.
`FlowContext.step` returns the JSON a replay returns; step keys are unique per run and
deterministic; results are capped at 256 KiB. `call`/`map_call` journal the child run id
before waiting, with the idempotency key `<run>/<key>/<attempt>`; a failed child fails the
step and the next attempt starts a new one. A parent holds its slot. A run that ends for
good without its output (CANCELLED, TIMED_OUT, or FAILED with no attempt left:
`STOPPED_PARENT_STATUSES`) cancels the children it still waited for, a fan-out's in-flight
siblings included, so they free their slots (`FlowContext.finish`, called by the host with
the final status); a run the host records RETRYING leaves them running, and its next
attempt re-attaches. `NonRetryable` exceptions fail a run without retry. A typed workflow that called
`ctx.skip()` returns `None` and ends SKIPPED; `WorkflowRun.result()` and a parent's `call`
then give `None`. Step keys reject control characters; a failed attempt's child is never
carried into the next attempt of a `call`. Retention deletes a run's journal before its record. Hosts publish
`{run_id, status}` on `JobSubjects.done` (core NATS, outside the jobs stream) when a run
is saved terminal; `CompletionNotices` waits on it with a 5 s poll fallback. A `Cron`/`Every`
`input` is the schedule body; its hash header is in `SCHEDULE_HEADERS` only when set, so
schedules from before it are not republished. Any new raw send is registered in core's
`nats_send_sites_test.py`. Tests: `tests/test_workflows.py`, and with `nats-server`
`tests/test_workflows_integration.py` (run both broker kinds with core importable).

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

### Declared actions and module scopes

Every agent, app and workflow of a module is a **module scope** a workspace grants one
item at a time (`module:<type>/<module_id>/<name>`, core `services/iam/AGENTS.md`,
"Module scopes"): Nexus checks it before a user reaches it, and workspace viewers and
members hold none by default. A module has nothing to do for those.

A module may also declare **actions of its own**: a catalog of resource types and
actions under its own service name, `catalog_service(module_id)` (`acme.people` is
`acme_people`). It is `Module.iam_catalog` (a dict), else `iam_catalog.yaml` beside the
module's code (`permissions.module_catalog`); `service` and `version` may be left out.
The catalog travels with the manifest (its `catalog` key, hashed with it), and IAM
registers it when an administrator approves the manifest: a changed catalog is a new
pending version. A catalog naming a kernel service, `iam`, `nexus`, `module` or another
module's service is refused at submission.

```yaml
# iam_catalog.yaml, beside the module
resource_types:
  - {name: brief, id: path, description: "A research brief."}
actions:
  - {name: ExportBrief, level: read, resource_types: [brief]}
```

The module enforces one for the call it serves, on the caller's context (during a run
for a user, both the user's grants and its own approved manifest must allow it):

```python
await self.require_action("ExportBrief", "brief", ["q3"])  # PermissionDenied / NotFound
decision, resource = await engine.services.iam.authorize_declared(
    "demo_research:ExportBrief", "brief", ["q3"]
)
```

IAM names the resource in the workspace of the call (`workspace=` to name another):
`abi:<org>:<ws>:demo_research:brief/q3`. A user needs a grant such as
`demo_research:ExportBrief` on `${scope}:demo_research:brief/*`, attached at the
workspace. The standalone demo (`examples/standalone_module/discovery_demo.py`) declares
and enforces one (`make demo-sdk`).

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
  own): `CallContext.delegated_token`, with the workspace of the submit
  (`SubmitRequest.context.workspace_id`, the turn's: Nexus sends it), so IAM places what
  the run does for the user there (`require_action`). Only the handler runs under it
  (`_Run.for_user`; a streaming handler is consumed whole by one task made in that
  context, `_UserStream`, so what it sets across a `yield` stays): the host's own records (the run, its events and output, the
  conversation claim) are the module's, as a workflow's bookkeeping is, since no user
  holds the module's documents. `Transport.delegated_token` sends it, in place
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

`integration.py`, `workflow.py`, `pipeline.py` (with `processes.py`: the shared
`Process` base, `as_tools`, construction) and `components.py` (names, discovery,
stdlib only) are the in-engine bases without core. Keep them importable without
extras: `components.py`, `integration.py` and `module.py` import neither pydantic,
rdflib nor LangChain (pydantic is imported by `processes.py`, rdflib by
`pipeline.py`, each raising an `ImportError` that names the extra; LangChain only
inside `as_tools`). The package `__init__` stays lazy. A component's name is
`component_slug(class name)`, mirroring core's `process_route_slug`: change them
together. `BaseModule` finds `Workflow`/`Pipeline` classes under `workflows/` and
`pipelines/` at class level (`get_workflow_classes`, `get_pipeline_classes`; names
unique per kind, one NATS subject token), and `run_module` validates them before
connecting. After `on_initialized` it builds each one (`New(module)`, else an empty
`<Name>Configuration`) unless `expose_workflow`/`expose_pipeline` bound it. An
agent takes its tools at construction, inside `on_initialized`, so
`build_processes()` is public and idempotent (locked): modules call it before
creating their agents, and `run_module`'s own call skips what is built; an
unbuildable, unbound class fails startup (its workflow is published, so callers
expect it). The in-process accessors are `get_workflow_instance`/`get_pipeline_instance`
(`get_workflow(name)` is the durable-workflow accessor).
The package is `module.__package__` (so `python -m pkg` works); a module in a top-level
script (`python worker.py`) has none, and its `workflows/` etc. are top-level packages
next to it (the folder is appended to `sys.path`). `serialize_result` is pydantic's
`to_jsonable_python`: models, dataclasses, datetimes, UUIDs and decimals nested in a
result are converted, an rdflib graph is `{"format": "text/turtle", "triples": n,
"data": ...}`.
Integrations are a pattern, never discovered. Tests:
`tests/test_process_classes.py` (extras: `--extra workflows --extra rdf --extra agents`,
a CI step) and `tests/test_workflows_extras.py` (no extras needed).

Workflow and Pipeline classes are durable workflows (`process_workflows.py`, Decision
(2026-10-26) below), published as core's
`EngineProcessBridge` publishes an engine module's classes: change them together. Each
class is `workflow.<slug>`/`pipeline.<slug>` (`process_workflow_name` in `jobs.py`), input
schema the parameters model's, output schema from the `run` annotation (`output_schema`),
description the docstring cut to 512 UTF-8 bytes, one step `run`. `encode_process_result`
journals the result: pydantic's JSON, a graph as `text/turtle` (`data` dropped with a
`note` above `MAX_RESULT_BYTES`, 60 KiB), anything else above it the `omitted` marker.
`job_settings` reads `Process.job` (a `JobSettings`: triggers and limits, default one
attempt and one run at a time; no `job` is no trigger). `check_classes`, run by
`run_module` before connecting, refuses a name already in `module_type.jobs` (an explicit
`@job`/`@workflow`/`jobs` entry), a `job` that is not a `JobSettings`, and a `Cron`/`Every`
input (default `{}`) the parameters model refuses; `run_module` also refuses a module with
classes but no discovery or no `document` service. `BaseModule.declare_process_workflows()`
declares them before `on_load`. The handler looks the bound instance up at run time, so a
run only starts once `build_processes` built it; an `OnEvent` run takes the event's `data`;
a refused input is `InvalidWorkflowInput` (no retry, field names only). Callers use
`get_workflow("workflow.<slug>")`; `WorkflowProxy.as_tools()` makes one LangChain tool of
any workflow. Tests: `tests/test_process_workflows.py` (no broker),
`tests/test_process_classes.py`, and the last two tests of
`tests/test_workflows_integration.py` (`nats-server`: a scheduled pipeline, a workflow
started from another module).

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

## Decision (2026-10-25): durable workflows on NATS

**Decision.** A workflow is a job with a schema and a journal (`workflows.py`): the jobs
runtime unchanged (consumer, run record, attempts, cancel, retention, Jobs tab), plus
`kind="workflow"` and JSON Schemas on `JobDescriptor`, a step journal in the module's
document namespace, child runs (`call`/`map_call`) journaled before the parent waits, and
completion notices on `JobSubjects.done`. `Cron`/`Every` may carry an `input`. Callers start
a workflow by name (`get_workflow(name)`: `start`/`run`). Engine modules get the same
runtime; see core's `naas_abi_core/module/AGENTS.md`.

**Consequences.**
- Runs are asynchronous and durable: a caller waits as long as it chooses, a run outlives
  its caller. A step result is at most 256 KiB, a run record keeps 64 KiB of output.
- Children are at least once: deduplication covers only the 2 minute JetStream window
  before the child run id is journaled. Child workflows should be idempotent.
- Step keys must be deterministic, and `map`/`map_call` items come in the same order on
  every attempt, or a replay runs steps again.
- A parent holds its slot while it waits: size `max_concurrency` for the parents that wait
  at once; a cycle through two workflows can deadlock (only a direct self-call is refused).
- A parent that ends for good (cancelled, timed out, failed with no attempt left) cancels
  the children it still waits for; one the host retries leaves them to its next attempt.
- Long waits (`sleep`, waiting for an event or an approval) are not supported.
- Not hosted without NATS, like jobs.

## Decision (2026-10-26): Workflow and Pipeline classes of a remote module

**Decision.** A remote module authors workflows, pipelines and integrations like an
in-engine module, on `naas_abi_sdk` only (`workflow.py`, `pipeline.py`, `integration.py`),
with an async `run`. Every `Workflow` and `Pipeline` class is published as a one-step
durable workflow, `workflow.<slug>` / `pipeline.<slug>`, exactly as core's
`EngineProcessBridge` publishes an engine module's classes: same names, input and output
schemas, and one result encoding (`process_workflows.py`, which core imports). There is one
way to run a workflow over NATS. An earlier draft served these classes over a request/reply
protocol of their own (per-caller authorization through discovery, a synchronous call
bounded by 300 s); it was dropped, and no proto message is added for them. `job =
JobSettings(...)` on a class gives its workflow triggers and limits. The module's own
agents use the built instances in process (`get_workflow_instance(name).as_tools()`).

**Consequences.**
- An SDK class, an engine class and a `@workflow` are started, listed, recorded and
  cancelled the same way, and callers name a class's workflow the same way wherever the
  module runs.
- Authorized per caller like any job: a start is a trigger the engine stores and the
  host authorizes (`discovery:TriggerJob` on `job/<project>/<module>/workflow.<slug>`), and a
  run started for a user runs for that user (see "Who a run runs as" under Jobs).
- Calls are durable runs, not synchronous calls. Every class gets one attempt and one run
  at a time unless its `job` says otherwise (a pipeline that wrote to the graph would write
  twice); in-process calls are not limited.
- A result over 60 KiB does not come back whole (a graph without its Turtle, anything else
  the `omitted` marker): a pipeline that must hand over more writes it to the triple store
  or object storage.
- Each class adds one workflow with its two schemas to the module's descriptor, which is
  capped at 64 KiB (each schema at 16 KiB): a module with many classes, or large parameter
  models, can be refused at registration, which names the limit.
- A module with these classes needs discovery and the `document` service.
- The kernel REST API does not mount remote workflows; use an in-engine module for that.

# naas-abi-sdk

Small, async Python clients for ABI engine services over NATS. Runtime dependencies:
`naas-abi-proto`, `protobuf` (transitive), and `nats-py`. No ABI core, LangChain,
Dagster, RDF library, database drivers, or HTTP framework.

```python
from dataclasses import dataclass
from naas_abi_sdk import BaseModule, ModuleConfiguration, ModuleDependencies


class ABIModule(BaseModule):
    @dataclass
    class Configuration(ModuleConfiguration):
        prefix: str = "my-module"

    dependencies = ModuleDependencies(services=("object_storage", "document"))

    async def run(self):
        storage = self.engine.services.object_storage
        await storage.put_object(self.configuration.prefix, "hello.txt", b"hello")
        content = await storage.get_object(self.configuration.prefix, "hello.txt")
        keys = await storage.list_objects(self.configuration.prefix)
        await storage.delete_object(self.configuration.prefix, "hello.txt")
        return content, keys
```

`engine.services` exposes async service methods accepting ordinary Python values
and returning bytes, lists, dictionaries, or portable SDK dataclasses from
`naas_abi_sdk.services.models`. Request construction and response conversion are
internal. Argument names and defaults follow the corresponding core methods where
the v1 contract supports them. No core classes are imported.

Explicit protobuf access remains available through `engine.rpc` or the low-level
`ABIClient`. Those clients cover all 117 v1 RPC endpoints in `catalog.py`.
Services: activity_log, cache, coding_environment, dataset, document, email, event,
keyvalue, object_storage, secret, source_control, triple_store, vector_store.
The bus retains its native publish/subscribe and enqueue/dequeue API, including
explicit `msg.ack()` after processing or `msg.nak()` on failure.

Use one client per asyncio event loop. Connections are lazy, shared by all services,
and released by the async context manager. `ABIClient.close()` only closes the
local connection. Explicit `vector_store.close(request)` and
`activity_log.shutdown(request)` are remote administrative operations; do not
call them to dispose of your client on a shared engine.

The token is an issued service JWT, or a synchronous `Callable[[], str]` that
supplies a refreshed token per request. The SDK never needs the engine's signing
key and does not depend on a JWT library. Broker credentials/TLS options can be
passed as nats-py connection keyword arguments. Service JWTs authenticate RPC
headers; they do not authenticate a connection to the broker or authorize native
bus subjects. Configure broker credentials and subject ACLs separately.

Default deadline: 10 seconds, covering connect and request. Each RPC is attempted
once. A timeout or lost connection may hide a completed write: reconcile before
retrying. Reconnect buffering is disabled. Requests include a trace ID and timeout;
this does not make server execution cancellable. Errors raise `RPCError` with
`code` and the original protobuf `response` for typed domain details. Native
transport exceptions and malformed protobuf errors propagate. The payload ceiling
is 8 MiB, or the broker's lower limit, including request headers.

The unary v1 contract does not serialize process-local model objects, ontology
execution, or arbitrary remote callbacks. Object and model facades use the
chunked transfer contract described below. Agent invocation
uses the separate contract described below. Cache v1 addresses
the engine's cold adapter by default; `cache.tier(index)` selects an explicit tier. Decorators remain local. Event v1 is the durable
log port; live messages use the bus. The engine's triple-store service rejects
`handle_view_event`, an adapter-internal callback, with `NOT_SUPPORTED`.

See `../../examples/standalone_module/README.md` for the executable full-surface
module and wheel-only dependency isolation check. Run `make deps test lint build`
for this package. Raw client generation is owned by the proto package's `make generate`.
Run `make generate` here to regenerate SDK DTOs and straightforward facade methods.

## Modules

A remote module exports `ABIModule`, extending the SDK's `BaseModule`. It has a
nested `Configuration`, a `ModuleDependencies` declaration, `self.engine.services`,
and `on_load`, `on_initialized`, `on_unloaded` hooks. The runner calls them in that
order around `run()`, and unloads/closes on failure or cancellation. Hooks may be
sync or async. `kv`/`events` aliases and `<service>_available()` checks are supported;
availability indicates a declared capability, not remote health or authorization.
Undeclared access fails explicitly. Module dependencies require discovery enabled.

Pass the module or a narrower service dependency into ordinary components:

```python
class ReportWriter:
    def __init__(self, module):
        self.storage = module.engine.services.object_storage
        self.prefix = module.configuration.prefix

    async def write(self, content: bytes):
        await self.storage.put_object(self.prefix, "report.txt", content)


# In ABIModule.on_initialized(): self.writer = ReportWriter(self)
```

When explicit injection is impractical, `current_module()` resolves the running
module for the current async task. It works inside lifecycle hooks, `run()`, child
tasks, and `asyncio.to_thread`. Concurrent instances of the same module class
remain isolated. There is no `get_instance()` registry. Calling it outside a
runner scope or after unload raises `RuntimeError`. Pass dependencies explicitly
to raw threads or callbacks without a copied context. Own and stop background
tasks in `on_unloaded`; context scoping does not cancel them automatically.

```python
from naas_abi_sdk import current_module


async def save_report(content: bytes):
    module = current_module()
    await module.engine.services.object_storage.put_object(
        module.configuration.prefix, "report.txt", content
    )
```

Install your module package alongside the SDK, supply `ABI_SERVICE_TOKEN` and
`ABI_NATS_URL`, then run `naas-abi-module my_module --config module.json`.
Alternatively call `await run_module(ABIModule, url=..., token=..., configuration=...)`.
The configuration file contains fields for your dataclass, not engine configuration
or signing credentials. `global_config` is a plain mapping.

Migration preserves module structure/lifecycle; it is not binary compatibility
with arbitrary engine modules. Change the base imports, declare service names
instead of core classes, use dataclass configuration, and await SDK operations
with ordinary Python arguments. Workflow/agent/FastAPI auto-discovery, live model objects,
and access to another module's Python objects are not silently emulated. Port business logic
separately from those framework-specific components.

`client.cache.tier(index)` addresses a configured cache tier by its order in the
engine's `services.cache.adapters` list. The default `client.cache` remains the
v1 cold endpoint. Tier contracts use the same protobuf messages, with subjects
`abi.svc.cache.v1.tier.<index>.<method>`.

## Document state and LangGraph checkpoints

Modules can declare `"document"`. `self.engine.services.document` binds requests
to the module's Python module name; it rejects rebinding and conflicting request
namespaces. Direct ABIClient users explicitly call
`client.document.for_namespace("my_package.agents")`. This is API scoping under
Stage 1 shared trust, not server-enforced per-module authorization.

Document RPCs cover collection declarations/list/drop, put/get/delete,
find/pagination, and count. `if_version=0` is create-only, positive versions are
compare-and-swap, and omission is unconditional. The document facade encodes and decodes Python dictionaries automatically;
bytes, datetimes and large integers retain their types. No database credentials are needed by clients.

Install `naas-abi-sdk[langgraph]` only in modules that run LangGraph:

```python
from naas_abi_sdk.langgraph import DocumentCheckpointSaver

# In your async ABIModule.on_initialized():
self.checkpointer = DocumentCheckpointSaver(
    self.engine.services.document, agent_id="reviewer-v1"
)
await self.checkpointer.setup()
self.graph = builder.compile(checkpointer=self.checkpointer)

# In an async module operation:
result = await self.graph.ainvoke(
    {"messages": [...]}, {"configurable": {"thread_id": conversation_id}}
)
```

Use `ainvoke`/`astream`; synchronous graph invocation is not supported by this
saver. It supports history, pending writes, interrupts/resume, and thread deletion.
A stable agent ID and module namespace let another process resume the same graph;
different agents remain isolated even when conversation IDs match. Run only one
execution per agent/thread at a time; shared persistence is not an execution lock.
Stop a thread's runs before deleting it. Metadata filtering is performed while
paging history; full snapshots remain subject to RPC payload limits.

Existing core agents keep their current PostgreSQL/memory selection. This optional
saver does not migrate old checkpoints, launch remote agents, or provide discovery.
See the document-checkpoint ADR and remote-agent invocation RFC for those boundaries.

## Facade compatibility boundaries

- All remote I/O is async. SDK dataclasses and exceptions are independent of core
  types; catch SDK service errors or `RPCError` and inspect its `code`.
- Cache reads visit configured tiers in order, writes select cold, and deletes
  visit all tiers. `cache.hot`/`cache.cold` and `await cache.hot_available()` use
  the authenticated `cache.describe` endpoint added with this SDK. Upgrade the
  engine alongside this SDK. Transport failures propagate; only cache misses and
  expiry cause tier fallback. Pickle and cache decorators are not supported.
- Install `[rdf]` for RDF graph/query results; the base package never imports
  rdflib eagerly. RDF callback subscriptions and schema helpers are not exposed.
- Events use SDK `Event(event_type, payload)` values instead of core ontology
  instances. Vector methods accept lists of floats. Raw cache/vector operations
  produce mutation audit events at the owner, matching in-engine callers.
- KV lock contexts, local model objects and framework-specific
  helpers have no equivalent here. Unsupported operations are not silently run
  locally. Use `engine.rpc` for administrative or lower-level contract operations.
- `current_module()` finds the current instance only. `engine.modules` resolves
  declared dependencies through discovery; `get_agent` returns an AgentProxy.

See `examples/standalone_module/user_module.py` at the repository root for a
protobuf-free module exercising the facades against a separate engine process.

## Module discovery

Configure exactly one engine to host the registry for a project:

```yaml
nats:
  nats_url: nats://127.0.0.1:4222
  jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
  discovery:
    project: default
    lease_seconds: 20
```

Without `discovery`, existing engine startup is unchanged. The registry needs
JetStream enabled and bucket permissions on its broker connection. It stores an
atomic bounded snapshot (256 live instances / 512 KiB) and verifies logical expiry
on every read. This first version supports one configured owner per project.
A separate process can host it through core's `start_discovery` factory.

```python
from naas_abi_sdk import (
    BaseModule,
    ModuleDependencies,
    AgentDescriptor,
    DiscoveryConfiguration,
    run_module,
)


class Provider(BaseModule):
    module_id = "acme.research"  # Stable even when launched as __main__.
    package_version = "1.0.0"
    agents = (AgentDescriptor("Researcher", "Find supporting evidence"),)

    async def run(self):
        await stop_event.wait()  # Your application's shutdown event.


class Consumer(BaseModule):
    module_id = "acme.consumer"
    dependencies = ModuleDependencies(modules=("acme.research",))

    async def on_initialized(self):
        research = self.engine.modules["acme.research"]
        self.agents = await research.list_agents()

    async def run(self):
        return self.agents


# In separate processes, using issued tokens:
# await run_module(Provider, url=url, token=token, discovery=DiscoveryConfiguration())
# await run_module(Consumer, url=url, token=token, discovery=DiscoveryConfiguration())
```

For package entrypoints the CLI accepts `--discovery-project default`. Registration
starts after on_load. Dependencies must become READY before on_initialized runs;
the default startup bound is 60 seconds, with 2-second dependency refresh. SDK
string dependencies currently request module contract major 1. Registration
publishes the module's explicit contract_major; clients can use DiscoveryClient
for explicit version lookup. Replicas of one contract declare identical dependency
and agent metadata. Changing that metadata requires a new contract major.

The heartbeat runs every 5 seconds (or a quarter lease for shorter leases), with
jitter. `module.discovery_status` exposes last-confirmed readiness and becomes
UNAVAILABLE after confirmation expires. Dependency loss yields DEGRADED on the
registry without killing independent module work. Every ModuleProxy lookup queries
fresh state; missing, incompatible and not-ready modules have distinct RPC error
codes. Recovery after lease loss uses a new instance identity. Unload marks
DRAINING and unregisters; a hard crash is handled by expiry.

`list_agents()` returns descriptors; `get_agent(name)` returns an invocable
proxy when its capability is registered. Legacy engine modules are not automatically
published. The Stage 1 trust model still allows trusted service identities
to register logical module names; declaration checks are not authorization.

Run the standalone demo to see a consumer wait, discover a provider's agent,
observe provider death, and recover after a replacement process registers.

## Remote agents

With discovery enabled, `await module.get_agent(name)` returns an `AgentProxy`.
The proxy preserves the Agent/IntentAgent prompt API with async network calls:

```python
research = self.engine.modules["acme.research"]
agent = await research.get_agent("Researcher")
answer = await agent.invoke("Explain the result")
async for event in agent.stream_invoke("Explain it step by step"):
    print(event["event"], event["data"])
```

Each proxy has `name`, `description` and `state.thread_id`. `duplicate()` creates
an independent conversation; `state.set_thread_id(...)` selects a stable one.
Intent matching stays in the owner process. Raw graphs, model clients, Python
callbacks and parent-graph handoffs are not serialized.

Providers declare the invocation capability and bind a handler before readiness:

```python
import asyncio
from naas_abi_sdk import BaseModule, ModuleDependencies, AgentDescriptor
from naas_abi_sdk.agent_host import InvocationContext


class Researcher:
    async def invoke(self, prompt: str, context: InvocationContext) -> str:
        return f"Received: {prompt}"


class ABIModule(BaseModule):
    module_id = "acme.research"
    dependencies = ModuleDependencies(services=("document",))
    agents = (
        AgentDescriptor(
            "Researcher", "Research a question", capabilities=("agent.invoke.v1",)
        ),
    )

    async def on_initialized(self):
        self.expose_agent("Researcher", Researcher())

    async def run(self):
        await asyncio.Event().wait()
```

A handler may also implement async `stream_invoke(prompt, context)`, yielding
`{"event": ..., "data": ...}` string pairs. Core SSE types (`message`, `done`,
`ai_message`, tool events and routing events) pass through unchanged. Without that
method, the host emits the completed invoke result as a message followed by done.
Streaming status reconstructs result text from message events joined by newlines;
`invoke()` preserves the handler's exact string result.

A module hosting an existing core Agent or IntentAgent can use:

```python
from naas_abi_core.services.agent.RemoteAgentAdapter import RemoteAgentAdapter

self.expose_agent("Researcher", RemoteAgentAdapter(existing_agent))
```

Only that provider needs ABI core. The adapter duplicates the agent with a scoped
thread ID and retains its configured checkpointer. It does not convert a synchronous
core graph to the async document checkpointer. Native async handlers can use
DocumentCheckpointSaver with `context.thread_id`, which is scoped to project,
module, agent and authenticated caller. The default SDK stays at four packages.

Install `[agents]` for `agent.as_tools()`. Use the resulting tool's `ainvoke` in
async LangGraph parents. Tools created inside the module event loop also support
synchronous core agent worker threads; they dispatch back to that loop. Calling
synchronous `tool.invoke` on the loop itself fails explicitly. Parent RunnableConfig
thread IDs propagate into separate remote conversations. Pass these as tools;
an AgentProxy is not an instance of the core Agent class for `agents=[...]` checks.

### Invocation status, replay and cancellation

```python
handle = await agent.submit("Research this", invocation_id="job-123")
status = await handle.status()
answer = await handle.result(timeout=120)

# Reattach after a lost reply or reconnect:
handle = agent.invocation("job-123")
async for event in handle.events(after_sequence=42):
    print(event)

# Explicit, cooperative cancellation:
await handle.cancel()
```

Submission uses a stable ID and document create-only/CAS operations. Repeating an
ID with identical caller, prompt, thread, mode and deadline returns the stored run;
changed input raises INVOCATION_CONFLICT. Ambiguous submission failures raise
SubmissionUncertain with a handle. There is no automatic invocation retry or
execution takeover. Status can be read through a replacement provider with the
same module/agent identity. A lost owner remains an unknown execution outcome,
not proof of failure. Live discovery does not guarantee a worker is making progress.

Conversation claims never expire automatically. Worker death or an ambiguous
storage write can leave one behind; reconcile the run and prove the old worker is
stopped before an operator removes a claim. Do not use the discovery lease to
unlock execution. This is intentionally conservative and is not exactly-once tool
side effects or a fenced failover scheduler.

Execution has no total deadline by default; an explicit deadline allows 1..3600
seconds. The provider also enforces a 300-second inactivity timeout, reset after
each persisted stream event. Configure it with
`run_module(..., agent_idle_timeout_seconds=600)` (positive and finite).
Non-streaming invocation must finish within that inactivity budget. Active streams
have no total-duration limit. Wait timeouts and
abandoning a stream do not cancel remote execution. Cancellation marks CANCELLING;
CANCELLED/TIMED_OUT is persisted only after execution stops. Synchronous core
inference cannot be forcibly interrupted: the adapter waits for its worker thread
before releasing the claim. Completed side effects cannot be undone. Graph
interrupt/resume is not yet part of this protocol.

The host admits at most 32 active runs per module. Prompts remain bounded to
64 KiB. Events and results are stored separately as immutable 8 KiB fragments;
there is no 64 KiB output limit or 1024-event cap. The run record holds committed
sequence counters and stays small. Status returns up to 64 event references;
the SDK retrieves and reconstructs their exact text, including UTF-8 boundaries.
The new wire format is explicitly negotiated (`output_format=2`); upgrade SDK
providers and consumers together. Older consumers fail with `UPGRADE_REQUIRED`
instead of receiving empty events. Existing inline records can still be read.

Records/fragments are retained until explicitly cleaned by an operator; no
automatic retention policy is installed, because deleting deduplication records
changes retry safety. Reserve `agent_runs_*`, `agent_claims_*`, and `agent_events_*`.
Interrupted writes can leave unpublished fragments, which must be cleaned with
their invocation after reconciliation. Status membership views cache for at most
one second; routing failures invalidate the caller cache without replaying calls.

Providers authenticate incoming issued tokens through discovery's authorize_agent
RPC using their own issued token and lease. Signing keys stay in the engine.
This forwards the caller's bearer token to the trusted provider for verification;
use broker TLS/ACLs. Stage 1 still lacks per-end-user/module grants, and document
namespaces are not security boundaries. Caller identity guards invocation status
and cancellation; declaration checks alone are not authorization.

## Remote models

Install `naas-abi-sdk[models]` to use models already registered by the engine's
provider modules. The engine exposes its model registry automatically when
its top-level NATS configuration is enabled. No additional model configuration
or provider credentials are needed in the consumer.

```python
from naas_abi_sdk import BaseModule, ModuleDependencies

class ABIModule(BaseModule):
    dependencies = ModuleDependencies(services=("model_registry",))

    async def run(self):
        registry = self.engine.services.model_registry
        registered = await registry.get_default_chat_model()
        chat = registered.model  # LangChain BaseChatModel proxy
        response = await chat.ainvoke("Explain this result")
        print(response.content)
        async for chunk in chat.astream("Explain it step by step"):
            print(chunk.content, end="")

        embedding = (await registry.get_default_embedding_model()).model
        vector = await embedding.aembed_query("A document to index")
        return vector
```

The module `timeout` controls each transport exchange, not total inference time.
Explicit model lookups use
`await registry.get_chat_model(canonical_id, provider=None)` or
`get_embedding_model(...)`; `get`, `list_models`, and `list_canonical_ids` are
also available. Like core, lookups return a wrapper whose `.model` is the usable
LangChain model. Pass `.model` to your agent. Core's NATS registry client returns
core wrappers automatically for existing local agents.

`chat.bind_tools([tool])` sends tool definitions; tool execution stays with your
agent. Tool calls/results, streamed tool arguments, usage metadata and portable
multimodal message content survive the boundary. Generic LangChain
`with_structured_output(schema)` uses tool calling and parses locally. Provider
support still determines which tools, formats and JSON generation options work.
Python callbacks, credentials, live model objects, and non-JSON provider options
cannot be sent. The proxy is not a provider-specific model subclass.

Sync `invoke`, `stream`, `embed_query` and `embed_documents` are supported from
worker threads while the module's event loop remains running. On that loop, use
async methods; otherwise a sync call would deadlock. No inference call is replayed
automatically. Transfers are ephemeral and have bounded packet queues. SDK model
inputs, results and streamed chunks are fragmented across broker-sized packets;
there is no 512 KiB logical-message ceiling or default total generation deadline.
Polling keeps an active generation alive even before its first token. Transfers
expire after 60 seconds without client activity by default.
Closing a stream requests cancellation, which cannot guarantee that provider
billing or synchronous work stops. Registry/model ownership stays with the
configured engine; publishing models from SDK provider modules is future work.

Runnable example: `examples/standalone_module/model_module.py`. `make demo-sdk`
launches it in a separate environment containing LangChain, SDK and proto, with
no ABI core installed. The base worker still verifies its four-package install.


## Object streams and transfer configuration

Object `get_object` uses chunked transfers; small byte `put_object` calls use one
unary RPC, while larger or streamed uploads use transfers. `get_object` still
returns all bytes in memory, matching the local API. For bounded reads:

```python
storage = module.engine.services.object_storage
with open("report.bin", "rb") as source:
    await storage.put_object_stream("reports", "report.bin", source)
async with storage.get_object_stream("reports", "report.bin") as source:
    async for chunk in source:
        await consume(chunk)  # or await source.read(65536)
```

For older object-storage owners, clients fall back to bounded unary operations
only when transfer-open reports no responders. Large objects still require an
updated owner; timeouts never trigger fallback or replay. Modern GET streams
fetch their first bounded fragment before entering the caller context, surfacing
missing objects early. Model transfers require updated owners. Existing
configurations need no new fields. Without a `nats` block, services remain local.
Optional engine settings (shown with defaults):

```yaml
nats:
  nats_url: "nats://127.0.0.1:4222"
  jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
  object_storage_streaming:
    chunk_bytes: 65536
    idle_seconds: 60
    max_sessions: 32
    max_upload_bytes: null
  models:
    generation_timeout_seconds: null
    streaming:
      chunk_bytes: 65536
      idle_seconds: 60
      max_sessions: 32
      max_upload_bytes: 16777216  # 16 MiB per model request
      max_buffered_upload_bytes: 67108864  # 64 MiB across retained model uploads
```

Chunk size is reduced for the broker's advertised packet limit. Uploads spool to
temporary disk and execute only after upload completion. Set `max_upload_bytes`
for object uploads if a deployment cap is needed. Model upload budgets are finite
and configurable, enforced before accepting each chunk. They bound serialized
input, not total generation duration or output length. Decoded protobuf and
provider objects require additional memory. Each domain limits active sessions and
buffers two output packets per session. Model providers and callers still hold
logical messages in memory; provider context windows still apply. Slow consumers
must read within the configured idle period. An optional generation deadline
covers execution, including output backpressure, after upload completion.

Cancellation closes streams and cleans temporary files; abandoned sessions expire.
Cleanup removes sessions immediately and retires them independently. Close and
host shutdown wait at most one second for cleanup. Synchronous backend work must
finish before its resources can be safely closed; deferred resources retain their
upload budget. At most `max_sessions` deferred cleanups are allowed before new
sessions are rejected. Backend socket timeouts remain necessary: Python cannot
kill a blocked thread, and interpreter exit can still wait for worker threads.
Transfers cannot resume after an owner restart and uncertain operations are never
replayed automatically. Original low-level unary endpoints, discovery records,
checkpoints and durable agent invocation records retain their own size limits;
chunking here covers object content and model inference payloads.


## Multiple engine owners and configuration checks

Stateless model/discovery requests and transfer opens use queue groups, so one
owner handles each request. Transfer IDs route subsequent packets to that owner;
legacy model stream requests are answered only by their encoded owner. Replicas
must share compatible model catalogs, service configuration and persistent stores.
This does not provide automatic domain placement, migration or inference failover.

NATS mode rejects an explicit non-NATS bus adapter or a bus URL different from
`nats.nats_url`. Omit the bus block to use NATS defaults, or configure
`services.bus.bus_adapter.adapter: nats_jetstream` with the matching URL.
`services.bus.emit_message_events` is preserved for engine bus facades. SDK native
bus operations still use the broker directly; they do not pass through BusService.
Mixed local/remote cache tiers are rejected: define the complete topology at its
owner rather than advertising tier indices that have no endpoint. Projects without
`nats` retain their existing adapter choices and wiring.

Heartbeats retry transient failures with exponential backoff and jitter, capped
after jitter at half the remaining confirmed lease (50 ms minimum retry interval).
Expired leases use half the nominal lease as the cap.
Authentication/configuration errors remain fatal and visible. Unexpected renewal
or endpoint-binding failures receive at most three consecutive attempts. Failed
endpoint rebinds clean up partial subscriptions and retain the previous bindings.

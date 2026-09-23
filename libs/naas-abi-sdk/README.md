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
`ABIClient`. Those clients cover all 110 v1 RPC endpoints in `catalog.py`.
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

The existing v1 contract has deliberate limits: no object streaming, process-local
model objects, agent/ontology execution, or remote callbacks. Cache v1 addresses
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
Undeclared access and unsupported cross-module discovery fail explicitly.

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
and direct access to another module are not silently emulated. Port business logic
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
  do not synthesize core ontology events.
- Object streaming, KV lock contexts, local model objects and framework-specific
  helpers have no equivalent here. Unsupported operations are not silently run
  locally. Use `engine.rpc` for administrative or lower-level contract operations.
- `current_module()` finds the current instance only. It does not discover other
  modules or provide an AgentProxy; cross-module dependencies still fail explicitly.

See `examples/standalone_module/user_module.py` at the repository root for a
protobuf-free module exercising the facades against a separate engine process.

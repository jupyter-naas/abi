# naas-abi-sdk

Small, async Python clients for ABI engine services over NATS. Runtime dependencies:
`naas-abi-proto`, `protobuf` (transitive), and `nats-py`. No ABI core, LangChain,
Dagster, RDF library, database drivers, or HTTP framework.

```python
import asyncio
import os
from naas_abi_sdk import ABIClient
from naas_abi_proto.object_storage.v1 import object_storage_pb2 as storage


async def main():
    async with ABIClient(
        "nats://localhost:4222", os.environ["ABI_SERVICE_TOKEN"]
    ) as abi:
        await abi.object_storage.put_object(
            storage.PutObjectRequest(
                prefix="demo", key="hello.txt", content=b"Hello from another process"
            )
        )
        result = await abi.object_storage.get_object(
            storage.GetObjectRequest(prefix="demo", key="hello.txt")
        )
        print(result.content)


asyncio.run(main())
```

Every method accepts a generated protobuf request and returns its generated response.
Explicit typed methods cover all 101 v1 RPC endpoints in `naas_abi_sdk/catalog.py`.
Services: activity_log, cache, coding_environment, dataset, email, event, keyvalue,
object_storage, secret, source_control, triple_store, vector_store. `abi.bus`
provides publish/subscribe and enqueue/dequeue using the engine's native subject,
stream, and durable-consumer conventions. Pull consumers require explicit
`msg.ack()` after successful processing or `msg.nak()` on failure.

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
for this package. Client generation is owned by the proto package's `make generate`.

## Modules

A remote module exports `ABIModule`, extending the SDK's `BaseModule`. It has a
nested `Configuration`, a `ModuleDependencies` declaration, `self.engine.services`,
and `on_load`, `on_initialized`, `on_unloaded` hooks. The runner calls them in that
order around `run()`, and unloads/closes on failure or cancellation. Hooks may be
sync or async. `kv`/`events` aliases and `<service>_available()` checks are supported;
availability indicates a declared capability, not remote health or authorization.
Undeclared access and unsupported cross-module discovery fail explicitly.

```python
from dataclasses import dataclass
from naas_abi_sdk import BaseModule, ModuleConfiguration, ModuleDependencies
from naas_abi_proto.object_storage.v1 import object_storage_pb2 as storage


class ABIModule(BaseModule):
    @dataclass
    class Configuration(ModuleConfiguration):
        prefix: str = "my-module"

    dependencies = ModuleDependencies(services=("object_storage",))

    async def run(self):
        await self.engine.services.object_storage.put_object(
            storage.PutObjectRequest(
                prefix=self.configuration.prefix, key="hello.txt", content=b"hello"
            )
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
with protobuf requests. Workflow/agent/FastAPI auto-discovery, live model objects,
and direct access to another module are not silently emulated. Port business logic
separately from those framework-specific components.

`client.cache.tier(index)` addresses a configured cache tier by its order in the
engine's `services.cache.adapters` list. The default `client.cache` remains the
v1 cold endpoint. Tier contracts use the same protobuf messages, with subjects
`abi.svc.cache.v1.tier.<index>.<method>`.

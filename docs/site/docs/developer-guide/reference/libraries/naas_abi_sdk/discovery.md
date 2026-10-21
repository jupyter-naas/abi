# discovery

## What it is
Portable discovery utilities for:
- Describing modules, agents, and models.
- Querying discovery/registry for module instances.
- Registering and renewing a module instance lease (heartbeat).
- Providing lightweight proxies to depend on other modules.

## Public API

### Data classes
- `AgentDescriptor`
  - Fields: `name`, `description`, `contract_major`, `capabilities`
- `ModelDescriptor`
  - Fields: `name`, `description`, `kind` (default `"chat"`)
- `ModuleInstance`
  - Fields: `module_id`, `instance_id`, `package_version`, `contract_major`, `status`, `expires_at`,
    `agents`, `jobs`, `dependencies`, `models`, `apps`, `tools` (`ToolDescriptor`s, see [tools](tools.md))
- `DiscoveryConfiguration`
  - Fields: `project="default"`, `startup_timeout=60`, `refresh_seconds=2`,
    `rollout_id=""`, `rollout_modules=()`
  - Validates project/timeouts/rollout settings in `__post_init__`.

### Functions
- `validate_rollout_id(value: str) -> str`
  - Validates rollout id format; raises `ValueError` if invalid.
- `module_descriptor(module_type, module_id: str, dependencies: tuple[str, ...]) -> pb.ModuleDescriptor`
  - Builds a `naas_abi_proto.discovery.v1.discovery_pb2.ModuleDescriptor` from a module type/object.
  - Pulls:
    - `module_type.package_version`, `module_type.contract_major`, `module_type.agents`
    - optional: `module_type.jobs`, `module_type.models`, `module_type.tools` (as `ToolDefinition`s; discovery validates them)
    - optional: `module_type.get_apps()` (if present)

### Classes

#### `DiscoveryClient`
Client for discovery RPCs via a `Transport`.

- `__init__(transport: Transport, project: str = "default")`
- `get_module(module_id: str, contract_major: int = 1) -> tuple[ModuleInstance, ...]`
  - Returns all instances for a module id/contract.
- `list_modules(*, limit: int = 100, after_instance_id: str = "") -> tuple[tuple[ModuleInstance, ...], str]`
  - Returns `(instances, next_after_instance_id)` for pagination.
- `evict(instance_id: str) -> ModuleInstance`
  - Admin-only: removes a registration immediately; next renewal fails with `LEASE_EXPIRED`.

#### `ModuleProxy`
Convenience wrapper around a specific `(module_id, contract_major)`.

- `instances() -> tuple[ModuleInstance, ...]`
- `ready_instances() -> tuple[ModuleInstance, ...]`
  - Filters instances with `status == "READY"`, else raises `RPCError("MODULE_UNAVAILABLE", ...)`.
- `list_agents() -> tuple[AgentDescriptor, ...]`
  - Returns agents from the first ready instance.
- `call_tool(name, arguments=None, *, config=None, timeout=None) -> Any`
  - Runs a tool a ready instance serves (one picked at random) and returns its JSON result. `timeout` is how long to wait and the handler's deadline. The module authorizes the caller (by default only the engine's own processes may).
- `get_agent(name: str)`
  - Returns an `naas_abi_sdk.agent.AgentProxy` if the agent exists and supports invocation:
    - `descriptor.contract_major == 1`
    - `"agent.invoke.v1"` in `descriptor.capabilities`
  - Else raises `RPCError("AGENT_NOT_FOUND" | "AGENT_NOT_INVOKABLE", ...)`.
- `get_job(name: str)`
  - Returns an `naas_abi_sdk.jobs.JobProxy` for a job found on the first ready instance.
  - Else raises `RPCError("JOB_NOT_FOUND", ...)`.
- `get_chat_model(name: str)`
  - Returns an `naas_abi_sdk.models.RemoteModel` backed by a ready instance that serves a chat model
    with `model.name == name` and `model.kind == "chat"`.
  - Else raises `RPCError("MODEL_NOT_FOUND", name)`.

#### `ModulesProxy`
Access and readiness-waiting for declared module dependencies.

- `__init__(client: DiscoveryClient, dependencies: tuple[str, ...])`
- `__getitem__(name: str) -> ModuleProxy`
  - Raises `ValueError` if `name` was not declared in `dependencies`.
- `wait_ready(config: DiscoveryConfiguration) -> None`
  - Polls until all dependency modules have at least one ready instance, or times out.
  - On timeout: raises `RPCError("DEPENDENCY_TIMEOUT", ...)`.

#### `DiscoverySession`
Lease-based registration/renewal loop for a module instance.

- `__init__(client: DiscoveryClient, descriptor: pb.ModuleDescriptor, rollout_id: str = "", rollout_modules: tuple[str, ...] = ())`
  - Generates `instance_id` and `lease_token`.
  - Exposes `drain_requested: asyncio.Event` (set when registry marks status as `"DRAINING"`).
- `current_status: str` (property)
  - Returns `self.status` if lease is still confirmed; otherwise `"UNAVAILABLE"`.
- `register() -> None`
  - Performs initial registration (or re-registration) and sets lease timing/status.
  - If `on_registered` is set, it is awaited after registration; used for endpoint binding.
- `start() -> None`
  - Calls `register()` and starts background heartbeat task.
- `renew() -> None`
  - Renews the lease; updates status and triggers drain event if `"DRAINING"`.
- `close() -> None`
  - Cancels heartbeat and attempts to unregister (failures are logged; lease will expire).
- Attributes commonly used by callers:
  - `initialized: bool` (sent on renew)
  - `draining: bool` (sent on renew; set when status becomes `"DRAINING"`)
  - `on_registered: Optional[Callable[[], Awaitable[None]]]` (async hook)

## Configuration/Dependencies
- RPC transport: `naas_abi_sdk.transport.Transport` is required for `DiscoveryClient`.
- Exceptions:
  - `naas_abi_sdk.transport.RPCError`
  - `nats.errors.Error` (as `NATSError`) for transport-level failures.
- Protocol buffers:
  - `naas_abi_proto.discovery.v1.discovery_pb2` (`pb`) for request/response/descriptor types.
- `DiscoveryConfiguration` enforces:
  - `project` matches `[A-Za-z0-9_-]{1,64}`
  - `startup_timeout` and `refresh_seconds` are finite and > 0
  - `rollout_id` format (or empty)
  - `rollout_modules` requires `rollout_id`, max 64 unique ids, validated format

## Usage

### Query modules and wait for dependencies
```python
import asyncio
from naas_abi_sdk.discovery import DiscoveryClient, DiscoveryConfiguration, ModulesProxy

async def main(transport):
    client = DiscoveryClient(transport, project="default")

    deps = ModulesProxy(client, dependencies=("naas.some.module",))
    await deps.wait_ready(DiscoveryConfiguration(project="default"))

    instances = await deps["naas.some.module"].ready_instances()
    print([i.instance_id for i in instances])

# asyncio.run(main(transport))
```

### Register a module instance (session + heartbeat)
```python
import asyncio
from naas_abi_sdk.discovery import DiscoveryClient, DiscoverySession, module_descriptor

async def main(transport, module_type):
    client = DiscoveryClient(transport, project="default")
    desc = module_descriptor(module_type, module_id="my.module", dependencies=())

    session = DiscoverySession(client, desc)
    await session.start()

    session.initialized = True  # will be sent on renew()

    # Wait until asked to drain
    await session.drain_requested.wait()
    session.draining = True

    await session.close()

# asyncio.run(main(transport, module_type))
```

## Caveats
- `ModuleProxy.list_agents()`, `get_job()`, and `get_agent()` rely on the *first* ready instance; if instances differ, results may vary.
- `DiscoverySession` heartbeat runs indefinitely until `close()`; failures may raise after repeated unexpected errors.
- `rollout_modules` cannot be set without a non-empty `rollout_id` (validated).

# BaseModule

## What it is
- A lightweight lifecycle runner for ABI modules, independent of the engine runtime.
- Provides:
  - Dependency-declared access to remote ABI services and other modules.
  - A structured startup/shutdown sequence (`on_load` → `on_initialized` → `run` → drain → `on_unloaded`).
  - Optional discovery registration, hosting for agents/models/tools/apps/jobs, and an optional health probe port.
  - A task-local `current_module()` context helper.

## Public API

### Data classes / configuration
- `ModuleDependencies(services=(), modules=())`
  - Declares which remote services (and other modules) this module is allowed to access.
- `ModuleConfiguration(global_config: dict[str, Any] = {})`
  - Base configuration type for modules.

### Service access / engine proxy
- `EngineProxy(client, dependencies, module_name="", discovery=None)`
  - Exposes:
    - `engine.services`: `ServicesProxy` (typed SDK service proxies with dependency checks)
    - `engine.rpc`: `RPCServicesProxy` (direct client access, same dependency checks)
    - `engine.modules`: `ModulesProxy | None` (requires discovery; for inter-module access)

- `ServicesProxy`
  - Attribute access to declared services only; raises `ValueError` if not declared.
  - Supports `*_available()` checks (e.g., `engine.services.document_available()`).
- `RPCServicesProxy`
  - Same dependency enforcement as `ServicesProxy`, but returns underlying (protobuf) clients.

### Module base class
- `class BaseModule(JobsMixin, Generic[Config])`
  - Subclass this to implement a module.

Key class attributes (override in subclasses):
- `Configuration = ModuleConfiguration`
- `dependencies = ModuleDependencies(...)`
- `module_id: str | None` (defaults to `module_type.__module__`)
- `package_version: str = "0.0.0"`
- `contract_major: int = 1`
- `agents: tuple[AgentDescriptor, ...] = ()`
- `models: tuple[ModelDescriptor, ...] = ()`
- `tools: tuple[ToolDescriptor, ...] = ()` (see [tools](tools.md): bind each with `expose_tool`)
- `apps: tuple[AppDescriptor, ...] | None = None`  
  - If `None`, apps are discovered from `apps/<name>/manifest.json` next to the package.

Instance properties:
- `engine -> EngineProxy`
- `configuration -> Config`
- `discovery_status -> str` (`DISABLED` if discovery not used)
- `health_port -> int | None` (set after health server starts)

Lifecycle hooks (sync or async):
- `on_load()`
- `on_initialized()`
- `on_unloaded()`
- `async run()` (must be implemented)

Exposure/binding APIs (call during `on_initialized`, before readiness):
- `expose_agent(name: str, handler) -> None`
  - Registers an async `handler.invoke(...)` for an `AgentDescriptor` that includes capability `"agent.invoke.v1"`.
- `expose_model(name: str, handler) -> None`
  - Registers an async `handler.invoke(...)` for a chat `ModelDescriptor` (`kind == "chat"`).
- `expose_tool(name: str, handler) -> None`
  - Binds a sync or async `handler(arguments)` (or `handler(arguments, call)`) for a declared `ToolDescriptor`. Arguments arrive validated against the input schema. Every declared tool needs a handler before readiness.
- `authorize_tool(name: str, caller: ToolCaller) -> bool` (override)
  - Whether `caller` may run the tool. Default: the engine's own processes only.
- `expose_app(name: str, asgi_app) -> None`
  - Binds an ASGI app (callable) to a declared/discovered app.
- `@classmethod get_apps() -> tuple[AppDescriptor, ...]`
  - Returns declared apps or discovered apps.

### Context helper
- `current_module() -> BaseModule`
  - Returns the module bound to the current task context.
  - Raises `RuntimeError` if called outside an active `run_module()` scope or after unload.

### Runner
- `async run_module(module_type, *, url, token, configuration=None, timeout=10.0, agent_idle_timeout_seconds=300.0, discovery=None, drain_timeout_seconds=300.0, health_port=None, health_host="", **connection_options) -> Any`
  - Creates the ABI client, applies dependency injection, manages discovery registration, starts relevant hosts, runs the module, and guarantees cleanup.
  - Installs SIGTERM/SIGINT handlers (when supported by the event loop) to request draining.

## Configuration/Dependencies

### Declaring service dependencies
- Set `dependencies = ModuleDependencies(services=(...), modules=(...))` on your module class.
- Access to undeclared services via `module.engine.services.<name>` (or `.rpc.<name>`) raises `ValueError`.
- Service aliases:
  - `"kv"` → `"keyvalue"`
  - `"events"` → `"event"`

### Discovery (optional but required for some features)
- Pass `discovery=DiscoveryConfiguration(...)` to `run_module()` when you need:
  - Inter-module dependencies (`ModuleDependencies.modules`)
  - Agent hosting, model hosting, app hosting
  - Job hosting (also requires `"document"` service dependency)

### Health probe port
- Enable by either:
  - Passing `health_port=...` to `run_module()`, or
  - Setting env `ABI_HEALTH_PORT` (integer 0–65535)
- Optional env override for bind host: `ABI_HEALTH_HOST` (default `0.0.0.0`)

### Rollout controls (when using discovery)
- Env/config inputs:
  - `ABI_ROLLOUT_ID`
  - `ABI_ROLLOUT_MODULES` (comma-separated)
- If rollout modules are set, a rollout id is required.

## Usage

```python
import asyncio

from naas_abi_sdk.module import BaseModule, ModuleConfiguration, ModuleDependencies, run_module

class MyConfig(ModuleConfiguration):
    pass

class MyModule(BaseModule[MyConfig]):
    Configuration = MyConfig
    dependencies = ModuleDependencies(services=("kv",))  # declare what you use

    async def run(self):
        # Access declared services via the engine proxy:
        if self.engine.services.kv_available():
            kv = self.engine.services.kv
            # ... use kv service methods here ...
        return None

async def main():
    await run_module(
        MyModule,
        url="nats://localhost:4222",
        token="YOUR_TOKEN",
        configuration=MyConfig(),
    )

if __name__ == "__main__":
    asyncio.run(main())
```

## Caveats
- `expose_agent` / `expose_model` require `handler.invoke` to be `async def`; otherwise `TypeError`.
- If any invocable agent is declared (`AgentDescriptor` with `"agent.invoke.v1"`), a handler must be registered for each before readiness, or startup fails.
- If any chat model is declared (`ModelDescriptor(kind="chat")`), a handler must be registered for each before readiness, or startup fails.
- Agent hosting and job hosting require **both**:
  - `discovery` enabled, and
  - `"document"` included in `dependencies.services`
- `current_module()` only works within the active `run_module()` scope; detached tasks may fail after unload.

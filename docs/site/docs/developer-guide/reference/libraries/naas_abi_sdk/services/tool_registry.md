# ToolRegistryService

## What it is
- An async facade over the engine's **tool catalog** (list, get and search the tools the engine's modules published; read only) and **`invoke`**, which runs one of them *on the engine*.
- The catalog never builds a tool, and no reply holds a credential. A tool's config requirements name the keys it needs (`secret=True` for a credential); `availability` says which keys the engine still lacks.
- What a module sees and runs is decided by the engine from the module's identity, not by the request. A tool that requires scopes reads as not found until the operator grants them in `nats.tool_registry.module_scopes`; a tool that declares no scope is not run for a module until `nats.tool_registry.invoke.modules.<id>.unscoped_tools` lists it.

## Public API
- `class ToolRegistryService(client: ToolRegistryClient)`
  - `list_tools(*, modules=(), tags=(), available_only=False) -> list[ToolEntry]`: every visible tool, sorted by id. `modules`: the tool's module is one of them. `tags`: it has all of them.
  - `get_tool(ref: str) -> ToolEntry`: `<namespace>/<name>` (highest version) or `<namespace>/<name>@<version>`. Raises `ToolNotFound`.
  - `search_tools(query, *, limit=5, min_score=None, modules=(), tags=(), available_only=False) -> list[ToolMatch]`: best first, `limit` 1 to 50. Raises `ToolSearchUnavailable` when the engine has no embedding model or index.
  - `invoke(ref, arguments=None, *, config=None, secrets=None, version="", timeout=60) -> Any`: run the engine tool and return its JSON result. `config`: plain values for non-secret keys. `secrets`: a configuration key the definition marks `secret=True` -> the **name** of an engine secret; the engine resolves it only if `nats.tool_registry.invoke.modules.<id>.secrets` lists that name for this module, runs the tool with it, and never sends the value (a result that echoes it comes back `[redacted]`). A credential written in `config` is refused. `timeout` is the tool's deadline (at most 300 s); the call waits 5 s longer, so a slow tool gives the engine's `DEADLINE_EXCEEDED`, never a raw timeout. Raises `ToolNotFound`, `ToolPermissionDenied`, `ToolExecutionError` or `ServiceError` (`INVALID_ARGUMENT`, `PAYLOAD_TOO_LARGE`, `RESOURCE_EXHAUSTED`, `DEADLINE_EXCEEDED`); nothing is retried. Every call is named (`call_id`): cancelling the task that awaits `invoke`, or a wait that runs out, sends `cancel_tool`, and the engine stops the tool (a coroutine tool at its next `await`; a synchronous one is told through `current_cancellation()` and keeps running unless it polls it). The deadline stops it the same way. See `docs/adr/20261026_tool-call-cancellation.md`.
  - `as_tool(tool, *, config=None, secrets=None, timeout=60, name=None)`: a LangChain tool (`naas_abi_sdk.engine_tools.engine_tool`, extra `engine-tools`) whose calls are `invoke`, from a reference, a `get_tool` entry or a `search_tools` match. An SDK `Agent` binds it like any tool.
- Results are frozen dataclasses: `ToolEntry(definition, availability)`, `ToolMatch(definition, availability, score)` with a `tool_id`, `ToolDefinition` (id, namespace, name, version, module, description, `input_schema`, `output_schema`, tags, `config` requirements, `requires_workspace`, `required_scopes`, `remote`: served by an SDK module, see [tools](../tools.md)) and `ToolAvailability(available, missing_config)`.

## Configuration/Dependencies
- Declare `ModuleDependencies(services=("tool_registry",))`.
- Wraps the generated `ToolRegistryClient` (`abi.svc.tool_registry.v1`). See `docs/adr/20261021_tool-catalog-over-nats.md` and, for `invoke`, `docs/adr/20261023_remote-callers-run-engine-tools.md`.
- The engine decides who may run what (operator config, deny by default):
  ```yaml
  nats:
    tool_registry:
      module_scopes: {my_module: ["github:read"]}
      invoke:
        modules:
          my_module:
            secrets: [GITHUB_ACCESS_TOKEN]
            unscoped_tools: ["naas_abi_marketplace.applications.github/get_*"]
  ```

## Usage
```python
class ABIModule(BaseModule):
    dependencies = ModuleDependencies(services=("tool_registry",))

    async def run(self):
        tools = self.engine.services.tool_registry
        for match in await tools.search_tools("report a bug", limit=3):
            print(match.tool_id, match.score, match.availability.available)
```

Run an engine tool, with a secret the module only names:

```python
tools = self.engine.services.tool_registry
issue = await tools.invoke(
    "naas_abi_marketplace.applications.github/create_issue",
    {"owner": "naas", "repo": "abi", "title": "Login fails"},
    secrets={"access_token": "GITHUB_ACCESS_TOKEN"},
)
```

Let an SDK agent bind what it found by search:

```python
from naas_abi_sdk.agents import Agent

found = await tools.search_tools("report a bug in a github repository", limit=3)
proxies = [
    await tools.as_tool(m, secrets={"access_token": "GITHUB_ACCESS_TOKEN"})
    for m in found
    if m.availability.available and not m.definition.remote
]
agent = Agent("support", "Opens issues", chat_model, tools=proxies)
```

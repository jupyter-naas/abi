# `engine_tools`

## What it is
A LangChain adapter for tools the **engine** holds: `engine_tool` wraps a tool definition (found by `get_tool` or `search_tools`) as a `StructuredTool` whose calls run the tool *on the engine* through [`ToolRegistryService.invoke`](services/tool_registry.md). An SDK `Agent` binds what it found by search like any tool.

The proxy holds the definition, the plain configuration and the **names** of engine secrets the caller chose, and nothing else: the engine builds and runs the tool, resolves its secrets, checks the module's verified identity and sends back JSON. See `docs/adr/20261023_remote-callers-run-engine-tools.md`.

## Public API
- `engine_tool(registry, tool, *, config=None, secrets=None, timeout=60, name=None) -> StructuredTool`
  - `tool`: a `ToolDefinition`, `ToolEntry` or `ToolMatch`. A `remote` definition (served by an SDK module) is refused with `ValueError`: call that module with `ModuleProxy.call_tool`.
  - `config`: plain values for non-secret keys. `secrets`: a configuration key the definition marks `secret=True` -> the name of an engine secret. Both are fixed when the tool is built, so the model never sees them.
  - The tool's schema is the definition's JSON Schema; its name is the definition's (made safe for a model), or `name`.
  - A failure (`ToolNotFound`, `ToolPermissionDenied`, `ToolExecutionError`, a refused argument, a busy engine) reaches the model as the tool's output (`ToolException`), so it can recover; the engine's messages hold no secret.
- `ToolRegistryService.as_tool(tool, ...)` does the same and fetches the definition when given a reference.
- `tool_output(result)`: a string as it is, any other JSON value as JSON.

## Configuration/Dependencies
- Extra `engine-tools` (`langchain-core`); an SDK `Agent` also needs `agent` (`langgraph`).
- The module declares `ModuleDependencies(services=("tool_registry",))`. What it may run is the operator's decision: `nats.tool_registry.module_scopes`, `invoke.modules.<id>.secrets` and `unscoped_tools`, all empty by default.

## Usage
```python
found = await tools.search_tools("report a bug in a github repository", limit=3)
proxies = [
    await tools.as_tool(m, secrets={"access_token": "GITHUB_ACCESS_TOKEN"})
    for m in found
    if m.availability.available and not m.definition.remote
]
agent = Agent("support", "Opens issues", chat_model, tools=proxies)
```

## Caveats
- Create the tool inside the running module: a synchronous `tool.invoke` is handed to the module's event loop and fails on that loop itself (use `ainvoke` there).
- A call is one attempt: a tool may have side effects, so nothing is retried. The deadline (`timeout`, at most 300 s) releases the caller; a synchronous engine tool keeps running to its end.

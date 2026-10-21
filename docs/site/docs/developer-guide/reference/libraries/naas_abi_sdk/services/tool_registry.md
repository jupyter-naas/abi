# ToolRegistryService

## What it is
- An async facade over the engine's **tool catalog**, read only: list, get and search the tools the engine's modules published.
- It never builds or runs a tool, and no reply holds a credential. A tool's config requirements name the keys it needs (`secret=True` for a credential); `availability` says which keys the engine still lacks.
- What a module sees is decided by the engine from the module's identity, not by the request. A tool that requires scopes reads as not found until the operator grants them in `nats.tool_registry.module_scopes`.

## Public API
- `class ToolRegistryService(client: ToolRegistryClient)`
  - `list_tools(*, modules=(), tags=(), available_only=False) -> list[ToolEntry]`: every visible tool, sorted by id. `modules`: the tool's module is one of them. `tags`: it has all of them.
  - `get_tool(ref: str) -> ToolEntry`: `<namespace>/<name>` (highest version) or `<namespace>/<name>@<version>`. Raises `ToolNotFound`.
  - `search_tools(query, *, limit=5, min_score=None, modules=(), tags=(), available_only=False) -> list[ToolMatch]`: best first, `limit` 1 to 50. Raises `ToolSearchUnavailable` when the engine has no embedding model or index.
- Results are frozen dataclasses: `ToolEntry(definition, availability)`, `ToolMatch(definition, availability, score)` with a `tool_id`, `ToolDefinition` (id, namespace, name, version, module, description, `input_schema`, `output_schema`, tags, `config` requirements, `requires_workspace`, `required_scopes`) and `ToolAvailability(available, missing_config)`.

## Configuration/Dependencies
- Declare `ModuleDependencies(services=("tool_registry",))`.
- Wraps the generated `ToolRegistryClient` (`abi.svc.tool_registry.v1`). See `docs/adr/20261021_tool-catalog-over-nats.md`.

## Usage
```python
class ABIModule(BaseModule):
    dependencies = ModuleDependencies(services=("tool_registry",))

    async def run(self):
        tools = self.engine.services.tool_registry
        for match in await tools.search_tools("report a bug", limit=3):
            print(match.tool_id, match.score, match.availability.available)
```

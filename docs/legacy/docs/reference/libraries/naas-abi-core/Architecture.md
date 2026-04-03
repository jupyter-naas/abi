# Architecture

`naas-abi-core` is organized around Hexagonal Architecture (Ports and Adapters) plus a module runtime.

## Key Building Blocks

- **Engine**: loads config, resolves module dependencies, loads services, modules, and ontologies.
- **Modules**: self-contained units that declare dependencies and expose agents/workflows/pipelines.
- **Services**: infra-facing capabilities behind ports (triple store, vector store, secret, bus, object storage, key-value, cache).
- **Applications**: API, MCP server, terminal app, Dagster integration.

## Dependency Model

- Modules declare required modules and services using `ModuleDependencies`.
- Engine computes a topological load order.
- Soft dependencies are supported by suffixing module names with `#soft`.

## Runtime Lifecycle

1. Parse config (`config.yaml` or `config.<ENV>.yaml`).
2. Load module dependency graph.
3. Load only services required by enabled modules.
4. Load modules in dependency order.
5. Load ontologies into triple store (if available).
6. Call `on_initialized()` on every loaded module.

## Service Wiring

Services inherit from a shared base and can be wired together.

- `IEngine.Services.wire_services()` injects access to sibling services for `ServicesAware` implementations.
- Example: triple store can publish events on bus when triples are inserted/deleted.

## Practical Design Notes

- Keep business logic in modules and workflows, not inside adapters.
- Add new infrastructure by implementing adapter interfaces, then bind it via config.
- Prefer module boundaries over cross-cutting utility code for domain features.

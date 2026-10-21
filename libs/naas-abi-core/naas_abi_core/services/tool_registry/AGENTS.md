# Tool Registry Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/tool_registry/`. Canonical reference for agents.

## Purpose

Process-local catalog of the tools the modules *this process loads* publish, and the
tools SDK modules serve ("Tools served by SDK modules"), one registry per process,
with NATS too: see "Engine wiring". Its catalog
reads also cover the serving engine's tools on an engine that does not serve
("Catalog over NATS"), and SDK modules can run those tools on the engine
("Running engine tools for other processes"). Each tool has a serialisable
**definition** (stable id, description, input contract, owning module, config
requirements, required scopes) and a runtime **binding** that builds an
executable tool for a caller. Agents are composed from definitions
(`services/agent_composer`) and can discover tools at runtime by meaning
(`services/agent/CapabilityAgent.py`). Decision record:
`docs/adr/20260923_tool-registry-and-agent-composition.md`.

Tool ids are `<namespace>/<name>@<version>`: namespace is the publishing
module's configured name (`naas_abi_marketplace.applications.github`), name is
the model-facing tool name, version is `MAJOR[.MINOR[.PATCH]]`. A reference
may omit the version (`ns/name`) and then resolves to the highest version.

## Files

```
tool_registry/
├── ToolRegistryPort.py        # ToolId/ToolRef, ToolDefinition, ToolContext, ToolBinding, ToolListing/ToolFilter, ports, exceptions
├── ToolRegistryService.py     # in-memory registry + lazy fingerprinted indexing + search + optional catalog
├── RemoteToolSynchronizer.py  # discovery -> registry: publishes the tools SDK modules serve, drops them with the module
├── EngineToolInvoker.py       # runs an engine tool for another process (invoke_tool): identity-bound access, secrets, scrubbing, limits
├── ToolAccessPolicy.py        # ScopeToolAccessPolicy (default)
├── ToolRegistryFactory.py     # InMemory(...), VectorStore(...)
├── adapters/
│   ├── tool_registry_nats_codec.py            # registry objects <-> abi.tool_registry.v1 messages, request limits
│   ├── primary/LangChainToolPublisher.py      # ToolPublisher, StaticToolBinding, FactoryToolBinding
│   ├── primary/RemoteToolBinding.py           # a tool a module serves, as a LangChain tool that calls it over NATS
│   ├── primary/tool_registry__primary_adapter__NATS.py  # the serving engine's catalog over NATS, and invoke_tool
│   └── secondary/
│       ├── ToolRegistrySecondaryAdapterNATSClient.py  # IToolCatalogPort over NATS (client / standby engines)
│       ├── RemoteToolsSecondaryAdapterNATS.py  # IRemoteToolDirectory (discovery) + IRemoteToolInvoker (abi.tool.v1)
│       ├── InMemoryToolIndexAdapter.py        # numpy cosine index (default)
│       ├── VectorStoreToolIndexAdapter.py     # index in the engine's VectorStoreService (UUID point ids)
│       └── ModelRegistryEmbedderAdapter.py    # embeddings from the model registry (batches of 1024, one lookup per sync)
└── tests/
    ├── tool_index__secondary_adapter__generic_test.py  # IToolIndexPort contract
    ├── concept_embeddings.py                           # deterministic embedding fixtures
    └── ToolRegistry_real_embedding_smoke_test.py       # Ollama nomic-embed-text (skips if absent)
```

## Port (`ToolRegistryPort.py`)

```python
class IToolRegistry:
    publish(module, tools: Sequence[PublishedTool])      # replaces the module's previous set
    unpublish(module)
    get_definition(ref) -> ToolDefinition                # ToolNotFoundError
    list_definitions(context=None) -> list[ToolDefinition]
    availability(ref, config=None) -> ToolAvailability    # missing required config
    check_access(ref, context, action) -> ToolDefinition  # ToolAccessDeniedError
    resolve(ref, context, config=None, action=EXECUTE) -> object   # executable tool
    search_tools(query, context=None, limit=5, min_score=None, where=None) -> list[ToolSearchResult]
    sync_index() -> int                                   # definitions (re-)embedded

class IToolCatalogPort:    list_tools(filter), get_tool(ref), search_tools(query, limit, min_score, filter) -> ToolCatalogSearch(results, truncated)   # another process's catalog, read only; raises ToolCatalogError
class IRemoteToolDirectory: list_modules() -> [RemoteModuleTools]   # modules with a READY instance that declare tools; RemoteToolDirectoryError
class IRemoteToolInvoker:   invoke / ainvoke(definition, contract_major, arguments, config, context)   # one attempt; RemoteToolError(code)
class IToolIndexPort:      prepare(model_key), fingerprints(ids), upsert(entries), delete(ids), search(vector, limit), size(),
                           collect_garbage(keep_ids)          # the writer's cleanup, never automatic
class IToolEmbedderPort:   model_key, embed_documents(texts), embed_query(text), resolve() -> ResolvedEmbedder  # model looked up once
class IToolAccessPolicy:   check(definition, context, action)   # raises ToolAccessDeniedError
class ToolBinding (Protocol): default_config; create(context, config) -> object
```

Exceptions (all `ToolRegistryError`): `InvalidToolReferenceError`,
`ToolNotFoundError`, `ToolAlreadyPublishedError`, `ToolAccessDeniedError`,
`ToolConfigurationError` (`.missing`), `ToolResolutionError`,
`ToolSearchUnavailableError`, `ToolCatalogError` (the other process's catalog
could not answer; `ToolCatalogRequestError` when it refused the request).

## Service behaviour (`ToolRegistryService.py`)

- **Publication** replaces a module's tool set atomically; a failed publish
  leaves the previous set. Definitions must belong to the publishing module;
  an id owned by another module is rejected.
- **Resolution** merges the binding's `default_config` (module-level values,
  never exposed) with the caller's config, checks the access policy, then
  required config, then builds. Binding failures become `ToolResolutionError`.
- **Search** embeds the query, over-fetches from the index (widening until
  the limit is met or a short page shows the index is exhausted; it does not
  trust `size()`), drops hits the
  caller may not discover, hits it does not know (another process's, or a
  previous run's: **never deleted**, the index may be shared) and those rejected
  by the optional `where` filter (e.g. an agent's allow list), and returns
  `limit` results sorted by cosine similarity. It never builds or grants a tool. No default score
  threshold: real-model margins are too narrow for one.
- **Indexing** is lazy (first search or `sync_index()`), so boot never
  depends on an embedding provider. A definition's fingerprint hashes
  `embedding_text()` + the embedder's `model_key`: new/changed definitions are
  embedded, unchanged ones skipped (also across restarts with a persistent
  index), removed ones deleted (only ids this registry indexed itself), and an
  embedding model change re-embeds all. The model is resolved once per sync or
  search (`embedder.resolve()`).
- `configure_search(embedder, index, collect_leftovers=False)` installs the
  backend (the engine does it in `EngineConfiguration_ToolRegistryService.wire`).
  `collect_leftovers=True` lets the first sync call `index.collect_garbage`;
  set it only for the sole writer of the index's storage.
- **Catalog.** `configure_catalog(IToolCatalogPort | None)` (the engine does it
  by role, see below). With one, `get_definition`, `list_definitions`,
  `availability`, `check_access` and `search_tools` cover this process's tools
  and the catalog's: a tool held here shadows the catalog's of the same id and a
  reference resolves here first; `search_tools` merges both rankings by score (it takes one view of the tools held when the
  search begins, so a tool published meanwhile is ranked by one half, never dropped by both),
  and the caller's `context` and `where` apply to what the catalog returned
  (it asks for more, doubling up to 50, until the limit is met, the catalog is
  exhausted (short and not `truncated`) or more brings nothing new). If the
  catalog fails (`ToolCatalogError`), `list_definitions` and `search_tools` go on
  with what this process holds (warning) and raise only when it holds nothing or
  could not rank it; `get_definition` and `availability` on a miss raise.
  A reply cut at the primary's byte budget is a known bound: what follows the cut
  is unreachable by search. `resolve` never
  leaves the process: for a tool only the catalog shows it raises
  `ToolResolutionError`. `get_local`, `list_local` and `search_local` read this
  process only: the NATS primary answers from them, so it never calls itself.
  `search_local` takes a `ToolFilter` (modules, tags, `available_only`).

## Publishing tools from a module

The engine calls `module.publish_tools(publisher)` for every module after
`on_initialized`, under the module's configured name. The default publishes
the discovered `self.tools` (`BaseTool` / `Expose` instances). Override it to
publish integrations; credentials stay module defaults or caller-provided
config, never part of a definition:

```python
def publish_tools(self, publisher):
    super().publish_tools(publisher)
    publisher.add_factory(
        lambda config: as_tools(MyIntegrationConfiguration(api_key=config["api_key"])),
        default_config={"api_key": self.configuration.api_key},
        requirements=[ConfigRequirement(key="api_key", secret=True)],
        tags=("crm",),
    )
```

`add_factory` calls the factory once to read definitions (missing required
keys get a placeholder), so the factory must not do I/O when building tools.
Example: `naas_abi_marketplace/applications/github/__init__.py`.

## Engine wiring

Always loaded (like the model registry) and exempt from
`ModuleDependencies`: `engine.services.tool_registry`, in every role. The
registry holds Python bindings, so it is **one per process**: bindings never
cross NATS, only its read-only catalog does (a micro service of the serving
engine, `tool_registry`); the modules each process loads publish to that
process's registry, after `on_initialized` and before module jobs start.

| Role | Registry | Search backend (`ToolIndexRole`) |
|---|---|---|
| NATS off | loaded by `EngineServiceLoader`, wired there | engine embedder + vector store; `PEER`: writes the shared index, collects nothing |
| serving | the owner's, carried into `module_services` by `EngineNATSDependencies.build()`; serves the catalog | NATS facades; `SOLE_WRITER`: shared index, collects leftovers |
| standby | same; reads the serving engine's catalog until the handover | NATS facades; `LOCAL` (in-memory index) until the handover, then `SOLE_WRITER` |
| client | created and wired by `Engine.__nats_clients()` / `build_clients()`; reads the serving engine's catalog | NATS facades; `LOCAL` |

`EngineNATSDependencies.wire_tool_registry(configuration, role)` wires the
search backend to the facades *after* `build()`, not to the owners; `Engine`
re-wires on fencing (`LOCAL`), restore and handover (`SOLE_WRITER`).
`EngineProxy.services.tool_registry` and `AgentComposerFactory.FromEngine` work
in all roles. Publication and `resolve` are local in every role; a client or
standby engine's reads also cover the serving engine's catalog.

### Catalog over NATS

`abi.svc.tool_registry.v1` (`naas_abi_proto/tool_registry/v1/tool_registry.proto`,
micro service `tool_registry`, ADR `docs/adr/20261021_tool-catalog-over-nats.md`)
has three **read only** operations, `list_tools`, `get_tool`, `search_tools`, and
`invoke_tool` ("Running engine tools for other processes"). The serving engine
starts `ToolRegistryPrimaryAdapterNATS` (in `EngineNATSLoader.expose_services`),
which answers the three reads from `*_local` and never resolves a binding or sends a
configuration value. Other engines read it with
`ToolRegistrySecondaryAdapterNATSClient`, which `wire_tool_registry` sets as the
registry's catalog for `ToolIndexRole.LOCAL` (client, standby before the
handover) and removes for `SOLE_WRITER` and `PEER`.

- **Scopes come from the verified service identity only** (`caller_context`):
  the engine's own processes (`api`, `engine`, `dagster`) hold every scope the
  catalog uses; an SDK module holds `nats.tool_registry.module_scopes[<module
  id>]`, none by default. The request's `CallContext` is not read and the proto
  has no scope field. A tool the caller cannot discover is `TOOL_NOT_FOUND`.
- **Validation is on the server** (no Protovalidate): limits in
  `tool_registry_nats_codec.py` (query 2000 characters, search limit 1..50,
  list limit 1..200, 32 module and 16 tag filters, reference 512), out of range
  is `INVALID_ARGUMENT`. A reply stays under half the broker's `max_payload`.
- Never put a binding value, a default config or a secret in a message: the codec
  (`definition_to_pb`) maps a `ToolDefinition` only; requirements carry key names.
- Tests: `adapters/primary/..._NATS_test.py` and `..._NATS_invoke_test.py` (no broker),
  `ToolRegistryCatalog_test.py` (registry with a catalog) and, on a real broker,
  `engine/Engine_tool_registry_nats_integration_test.py`.

### Running engine tools for other processes

ADR `docs/adr/20261023_remote-callers-run-engine-tools.md`. `invoke_tool` (same service) runs a
tool this engine holds, **on the engine**, for an SDK module or another engine process:
`InvokeToolRequest` has the fields of `abi.tool.v1.InvokeToolRequest` (`tool` reference, `version`,
`arguments_json`, `config_json`, `context`) and `secret_refs` (config key -> engine secret *name*).
Only JSON crosses the wire; no binding, callable or secret value.

- **Identity, never the request.** `ToolRegistryPrimaryAdapterNATS.invoke_caller(identity)` builds an
  `InvokeCaller` from the verified token: `api`, `engine`, `dagster` hold every scope, any secret, any
  tool, and only `api`/`engine` may name a user or workspace (`context.principal_id/workspace_id`,
  refused with `PERMISSION_DENIED` from anyone else). An SDK module holds nothing by default:
  `nats.tool_registry.module_scopes[<id>]`, `invoke.modules[<id>].secrets` (engine secret names it may
  reference) and `invoke.modules[<id>].unscoped_tools` (patterns of tools with no `required_scopes`
  it may run). A tool that declares no scope is **not run for a module** until listed (the GitHub
  tools publish none and run with the module's token by default).
- **`EngineToolInvoker`** (technology agnostic; the primary decodes) checks in order: sizes and user
  naming; the tool (not discoverable -> `TOOL_NOT_FOUND`; `remote` tools -> `PERMISSION_DENIED`, call
  the module; unscoped grant; the registry's `EXECUTE` policy); arguments against the JSON Schema; config
  (declared keys, plain values, **no value for a key marked `secret`**); secret refs (key marked
  secret, name on the allow list, checked before any lookup); admission; then on a worker thread under
  a deadline: resolve the secrets, `registry.resolve`, run.
- **Secrets never come back.** Results, a `ToolException` message and validation messages are scrubbed
  of the referenced secret values and the binding's credential defaults
  (`ToolRegistryService.credential_values`); any other tool failure is `TOOL_ERROR` "Tool execution
  failed" (type logged, never the message); one `tool_registry.invoke` activity event per call (tool,
  outcome, code, duration; no arguments, config or secret names).
- **Limits.** 512 KiB request, 256 KiB arguments, 64 KiB config, 16 refs, 512 KiB result;
  `nats.tool_registry.invoke: {enabled, max_concurrent (16, lowered with a warning to half of nats.max_concurrent_requests), default_timeout_seconds (lowered to max_timeout_seconds when above it),
  max_timeout_seconds, modules}`. Over the limit: `RESOURCE_EXHAUSTED` (retryable), never queued; a slot is
  held until the tool returns (a synchronous tool cannot be cancelled).
- **Not here:** a client engine's `resolve` of a tool it has not loaded still raises. The composer resolves
  `{secret: NAME}` against the client's own secrets, so a proxy would send credential values; the ADR says
  what it needs instead. SDK side: `ToolRegistryService.invoke` / `as_tool` (`naas_abi_sdk.engine_tools`).
- Tests: `EngineToolInvoker_test.py` (every refusal, scrubbing in results, errors, logs, activity),
  `adapters/primary/..._NATS_invoke_test.py` (identity -> rights), and on a real broker
  `engine/Engine_invoke_tools_nats_integration_test.py` (an SDK agent searches, binds and runs a
  GitHub-style tool with a secret reference resolved on the engine).

### Tools served by SDK modules

ADR `docs/adr/20261022_remote-module-tools.md`. An SDK module declares
`tools = (ToolDescriptor(...),)` and binds each with `expose_tool(name, handler)`;
discovery stores them in its descriptor (`ModuleDescriptor.tools`, the portable
`ToolDefinition`), and the module serves `abi.mod.<project>.<instance>.tool.<name>.invoke`
(`abi.tool.v1`: JSON arguments and result, one attempt, validated against the input schema
before the handler, sanitized errors, deadline, size caps).

- **In.** `RemoteToolSynchronizer` reads discovery every
  `nats.tool_registry.remote_modules.refresh_seconds` (5 s) and `publish`es each module with a
  READY instance as `<module_id>/<name>@<version>` (`ToolDefinition.remote = True`, binding
  `RemoteToolBinding`); a module with none is `unpublish`ed, and the index follows at the
  next search (`_sync` deletes what this registry indexed). A failed read keeps what is
  published. `EngineRemoteToolLoader` starts it after `publish_tools`, in every NATS role
  (serving, standby, client: bindings are per process), and `Engine.shutdown` stops it.
  A module named like a loaded module, or a tool another module holds, is not published.
- **Out.** `resolve` builds a `StructuredTool` whose schema is the module's JSON Schema; a
  call looks up a READY instance in discovery and sends one `InvokeToolRequest` as the
  `engine` identity with the caller's user and workspace (`ToolContext`). A module error is the
  tool's output (`ToolException`: the model can recover); nothing is retried.
- **Credentials.** No engine secret reaches a module: discovery refuses a secret
  requirement, a remote binding's `default_config` is empty and it refuses undeclared
  configuration keys, and the composer rejects `{secret: NAME}` on a `remote` definition
  (`AgentCompositionError`, also in `capabilities.tool_config`). A remote tool's config is plain
  values; the module holds its own credentials.
- Access and scopes are the registry's, as for local tools. Config:
  `nats.tool_registry.remote_modules: {enabled, refresh_seconds, call_timeout_seconds}`
  (needs `nats.discovery`). Tests: `RemoteToolSynchronizer_test.py`,
  `adapters/primary/RemoteToolBinding_test.py`, and on a real broker
  `engine/Engine_remote_tools_nats_integration_test.py`.

**Several processes on one vector store** (the sqlite_vec dev default shares a
file between `api` and `dagster`): an engine without NATS writes the shared
index but only deletes what it indexed itself. Engines that publish different
tools to one store (for instance a one-off `abi chat <module>` next to the API)
should use different `collection_prefix` values. Configuration
(`services.tool_registry`, all optional):

```yaml
tool_registry:
  index: auto              # auto (vector store if loaded, else memory) | memory | vector_store
  embedding_model: null    # canonical id; null = model registry default
  embedding_provider: null
  collection_prefix: abi_tool_registry
  search_enabled: true
```

## Factory (`ToolRegistryFactory.py`)

```python
ToolRegistryFactory.InMemory(
    model_registry=None, embedding_model=None, access_policy=None
)
ToolRegistryFactory.VectorStore(
    vector_store,
    model_registry,
    embedding_model=None,
    collection_prefix=...,
    access_policy=None,
)
```

## Tests

```bash
# the catalog, the tools SDK modules serve and engine tools run remotely, over a real broker (nats-server on PATH; fails instead of skipping):
ABI_REQUIRE_NATS_SERVER=1 uv run pytest libs/naas-abi-core/naas_abi_core/engine/Engine_tool_registry_nats_integration_test.py libs/naas-abi-core/naas_abi_core/engine/Engine_remote_tools_nats_integration_test.py libs/naas-abi-core/naas_abi_core/engine/Engine_invoke_tools_nats_integration_test.py -o addopts=""
uv run pytest libs/naas-abi-core/naas_abi_core/services/tool_registry -o addopts=""
# real embeddings (skips unless Ollama serves nomic-embed-text):
uv run pytest libs/naas-abi-core/naas_abi_core/services/tool_registry/tests/ToolRegistry_real_embedding_smoke_test.py -o addopts=""
```

## Adding a new index adapter

1. Implement every `IToolIndexPort` method in `adapters/secondary/<Name>ToolIndexAdapter.py`.
2. `prepare(model_key)` must stop showing vectors of another model, and must **not delete** what a process sharing the storage may have written (it only selects). Removal of leftovers is `collect_garbage(keep_ids)`, run by the sole writer. Storage is created on first `upsert`, sized from its vectors; mismatched dimensions raise `ValueError`; calls before `prepare` raise `RuntimeError`.
3. Add `<Name>ToolIndexAdapter_test.py` subclassing `ToolIndexSecondaryAdapterContract` with an `index` fixture.
4. Offer it in `EngineConfiguration_ToolRegistryService.index` if the engine should select it.

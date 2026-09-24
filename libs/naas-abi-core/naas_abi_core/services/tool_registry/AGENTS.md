# Tool Registry Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/tool_registry/`. Canonical reference for agents.

## Purpose

Process-wide catalog of the tools modules publish. Each tool has a serialisable
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
├── ToolRegistryPort.py        # ToolId/ToolRef, ToolDefinition, ToolContext, ToolBinding, ports, exceptions
├── ToolRegistryService.py     # in-memory registry + lazy fingerprinted indexing + search
├── ToolAccessPolicy.py        # ScopeToolAccessPolicy (default)
├── ToolRegistryFactory.py     # InMemory(...), VectorStore(...)
├── adapters/
│   ├── primary/LangChainToolPublisher.py      # ToolPublisher, StaticToolBinding, FactoryToolBinding
│   └── secondary/
│       ├── InMemoryToolIndexAdapter.py        # numpy cosine index (default)
│       ├── VectorStoreToolIndexAdapter.py     # index in the engine's VectorStoreService (UUID point ids)
│       └── ModelRegistryEmbedderAdapter.py    # embeddings from the model registry
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

class IToolIndexPort:      prepare(model_key), fingerprints(ids), upsert(entries), delete(ids), search(vector, limit), size()
class IToolEmbedderPort:   model_key, embed_documents(texts), embed_query(text)
class IToolAccessPolicy:   check(definition, context, action)   # raises ToolAccessDeniedError
class ToolBinding (Protocol): default_config; create(context, config) -> object
```

Exceptions (all `ToolRegistryError`): `InvalidToolReferenceError`,
`ToolNotFoundError`, `ToolAlreadyPublishedError`, `ToolAccessDeniedError`,
`ToolConfigurationError` (`.missing`), `ToolResolutionError`,
`ToolSearchUnavailableError`.

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
  caller may not discover, stale ids and those rejected by the optional `where`
  filter (e.g. an agent's allow list), and returns `limit` results sorted by
  cosine similarity. It never builds or grants a tool. No default score
  threshold: real-model margins are too narrow for one.
- **Indexing** is lazy (first search or `sync_index()`), so boot never
  depends on an embedding provider. A definition's fingerprint hashes
  `embedding_text()` + the embedder's `model_key`: new/changed definitions are
  embedded, unchanged ones skipped (also across restarts with a persistent
  index), removed ones deleted, and an embedding model change re-embeds all.
- `configure_search(embedder, index)` installs the backend (the engine does
  it in `EngineConfiguration_ToolRegistryService.wire`).

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
`ModuleDependencies`: `engine.services.tool_registry`. Configuration
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
uv run pytest libs/naas-abi-core/naas_abi_core/services/tool_registry -o addopts=""
# real embeddings (skips unless Ollama serves nomic-embed-text):
uv run pytest libs/naas-abi-core/naas_abi_core/services/tool_registry/tests/ToolRegistry_real_embedding_smoke_test.py -o addopts=""
```

## Adding a new index adapter

1. Implement every `IToolIndexPort` method in `adapters/secondary/<Name>ToolIndexAdapter.py`.
2. `prepare(model_key)` must discard vectors of another model; storage is created on first `upsert`, sized from its vectors; mismatched dimensions raise `ValueError`; calls before `prepare` raise `RuntimeError`.
3. Add `<Name>ToolIndexAdapter_test.py` subclassing `ToolIndexSecondaryAdapterContract` with an `index` fixture.
4. Offer it in `EngineConfiguration_ToolRegistryService.index` if the engine should select it.

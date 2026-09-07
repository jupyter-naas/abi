# Model Registry Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/model_registry/`. Canonical reference for agents. Also see `README.md`.

## Purpose

Process-wide catalog of LLM **chat** and **embedding** models. Modules register concrete models under a **canonical ID** (e.g. `claude-sonnet-4.5`) at load time; callers ask for `get_chat_model("claude-sonnet-4.5")` without knowing the provider. Off-catalog lookups fall back to registered **provider factories**.

## Files

```
model_registry/
├── ModelRegistryPort.py      # IModelRegistry, exceptions, factory type aliases
├── ModelRegistryService.py   # in-memory implementation
├── ModelRegistryFactory.py   # InMemory(...)
├── ModelRegistryService_test.py
└── README.md                 # architectural docs
```

## Port (`ModelRegistryPort.py`)

```python
class IModelRegistry: ...

# Exceptions
ModelNotFoundError
ProviderNotConfiguredError
DefaultModelNotResolvedError

# Type aliases
ChatProviderFactory      = Callable[[str], BaseChatModel]
EmbeddingProviderFactory = Callable[[str], Embeddings]
```

## Service API (`ModelRegistryService.py`)

```python
register(canonical_id, model)
register_chat_provider(provider, factory: ChatProviderFactory)
register_embedding_provider(provider, factory: EmbeddingProviderFactory)

get(canonical_id, provider=None) -> Model
get_chat_model(canonical_id, provider=None) -> ChatModel              # raises if wrong type
get_embedding_model(canonical_id, provider=None) -> EmbeddingModel    # raises if wrong type

default_chat_model_id -> str | None       # configured default canonical id (property, never raises)
default_embedding_model_id -> str | None   # configured default canonical id (property, never raises)

get_default_chat_model() -> ChatModel
get_default_embedding_model() -> EmbeddingModel
validate_defaults()         # called at engine startup

list_models() -> list[Model]
list_canonical_ids() -> list[str]
```

## Adapters

None. The registry uses LangChain's `BaseChatModel` / `Embeddings` directly. Off-catalog providers are registered as callables.

## Factory (`ModelRegistryFactory.py`)

```python
ModelRegistryFactory.InMemory(
    default_chat_model: str | None = None,
    default_embedding_model: str | None = None,
) -> ModelRegistryService
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/model_registry/ModelRegistryService_test.py
```

Covers registration, provider pinning, fallback, off-catalog routing, defaults, introspection.

## Adding a new model / provider

- **Catalog** model (preferred for stable IDs): call `register(canonical_id, model)` at module load.
- **Off-catalog** model (provider knows how to build it on demand): call `register_chat_provider(provider, factory)` (or `register_embedding_provider`). The factory receives the canonical/model ID string and returns the live instance.
- Always call `validate_defaults()` at startup if you set defaults via `InMemory(default_chat_model=..., default_embedding_model=...)`.

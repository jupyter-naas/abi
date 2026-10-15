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

## Authorization (`iam_catalog.py`, RFC §6.4)

Wired with IAM (the engine's owner always is; the NATS client never is), every
operation is checked in the domain service, on `model/<canonical id>`
(platform-level). An invisible model is `ModelNotFoundError` (`MODEL_NOT_FOUND`).

- `get`, `get_chat_model`, `get_embedding_model` (and the defaults): `Resolve`.
- `list_models`, `list_canonical_ids`, `list_registered_models`: filtered by
  `ListModels`.
- Every invocation of a chat model the registry hands out needs `Chat`, in the
  context of the call that invokes it: a LangChain callback attached once per
  model (`_ChatGate`). Agents built once, at boot, as the engine are still
  checked for each user that chats.
- The NATS endpoint resolves a reference with `resolve_ref(..., action=)`, which
  checks only that operation's action (`Resolve`, `Chat`, `ChatStream`, `Embed`)
  and returns the run configuration marking the invocation as authorized, so
  the callback does not ask for `Chat` again. Remote callers never pass run
  configuration, so they cannot set that mark.
- In process, an embedding model is used directly once resolved: its use is
  checked as `Resolve`; `Embed` is checked over NATS.
- Registering models is boot work and is not checked.

## Remote registry and inference

`adapters/primary/model_registry_nats.py` wraps the owning IModelRegistry and
executes LangChain inference. `adapters/secondary/model_registry_client.py`
implements registry lookup over NATS, restores core model wrappers, and forwards
only bootstrap registration/validation to its local owner. `list_registered_models`
returns `(canonical_id, model)` entries for complete catalog publication.
EngineNATSLoader exposes the primary; EngineNATSDependencies injects the client.
The primary runs each call, and each stream, under the caller's `CallContext`
(`engine/nats_identity.py`, `engine/call_context.py`).
Never expose that client as a primary or route registration through inference RPCs.
Each provider call runs in a `model <operation> <canonical id>` span (identity,
input counts and reported token usage only: never messages, texts or options).

Contracts: `naas-abi-proto/naas_abi_proto/model_registry/v1/model_registry.proto`.
SDK optional model codec/proxies stay core-free; core's NATS extra installs them.
Tests: `uv run pytest examples/standalone_module/model_integration_test.py -q`
from repository root, with native `nats-server`. Run `make demo-sdk` for the
separate-process, wheel-installed model example. Defaults and limitations are
in `docs/adr/20260924_remote-model-registry.md`.

Independent requests use a queue group; stream/transfer IDs encode an owner.
Never randomly distribute reads of an existing stream across replicas. See
`20260924_nats-review-reliability.md` for routing and output persistence decisions.

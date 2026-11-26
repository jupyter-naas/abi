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

## Authorization (`iam_catalog.py`)

Wired with IAM (the engine's owner always is; the NATS client never is), every
operation is checked in the domain service, on `model/<canonical id>`
(opaque id, platform-level). An invisible model is `ModelNotFoundError`
(`MODEL_NOT_FOUND`). The guard is described in
[`services/iam/AGENTS.md`](../iam/AGENTS.md) ("Enforcing in a domain service").
Levels: `ListModels` list; `Resolve`, `Chat`, `ChatStream`, `Embed` read. Subjects
are the operations under `abi.svc.model_registry.v1.` (`list_models`, `resolve`,
`chat`, `embed`; `ChatStream` is one action for `stream_open`, `<owner>.stream_next`
and `<owner>.stream_close`; a large call also uses the `transfer.*` subjects).

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
- **An agent's own model** (`agent_models.py`). No role reaches a model (core
  `roles.py`: no `model_registry` row in the platform policies); a person's
  models are a model set's. The in-process caller that runs a module agent's turn
  (Nexus's `provider_runtime.agents_own_models`) wraps it in
  `agent_models(action, {canonical id: [agent scope names]})`: inside it,
  `Resolve`, `Chat` and `ChatStream` on a model the agent owns are authorized as
  `action` (`module:UseAgent`) on one of its scopes for the caller, instead of
  the model's own action. Any other model, and `Embed`, stay the caller's. A
  context variable, set in process only; `gated_model_ids(model)` reads which
  models an agent was built with from the registry's gates.
- **A host's substitute** (`register_model_substitute`, `substitute_chat_model`).
  The host (Nexus) may say which chat model a container uses instead of the one
  asked: `(container, canonical id) -> canonical id`, or `PermissionDeniedError`
  to refuse it there. The NATS primary asks it with the request's container
  before it resolves a chat model (`resolve`, `chat`, `chat_stream`) and drops the
  pinned provider and variant when it switches; never for an embedding. In-process
  turns are the host's to retarget (it holds their models). Core does not know why
  (Nexus: a workspace's offer, ADR `20261126_models_in_the_offer`).

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

A chat's options reach the provider only when listed (`GENERATION_OPTIONS`:
`temperature`, `top_p`, `max_tokens` up to `MAX_TOKENS_LIMIT`, `seed`,
`response_format`; `TOOL_OPTIONS` for `bind_tools`: `tool_choice`,
`parallel_tool_calls`, `strict`), each value checked. Anything else (the
provider's model, endpoint, headers, extra bodies, `n`, `stop` outside the
request's own field) is refused with `INVALID_ARGUMENT`: IAM authorizes the
registered model, and the call goes to that model only.

Contracts: `naas-abi-proto/naas_abi_proto/model_registry/v1/model_registry.proto`.
SDK optional model codec/proxies stay core-free; core's NATS extra installs them.
Tests: `uv run pytest examples/standalone_module/model_integration_test.py -q`
from repository root, with native `nats-server`. Run `make demo-sdk` for the
separate-process, wheel-installed model example.

Independent requests use a queue group; stream/transfer IDs encode an owner.
Never randomly distribute reads of an existing stream across replicas.

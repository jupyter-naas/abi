# ModelRegistry

A process-wide catalog of chat and embedding models contributed by provider
modules at load time. Callers ask for a model by an **ABI-level canonical
id** (e.g. `claude-sonnet-4.5`) and get back a typed `ChatModel` /
`EmbeddingModel` whose underlying LangChain client already has the right
api key, region, and provider-specific model id wired in.

The point is to make this work without any caller knowing where the model
ships from:

```yaml
# config.yaml
modules:
  - module: naas_abi
    config:
      abi_agent_model: "claude-sonnet-4.5"   # any registered canonical id
```

```python
abi_module.engine.services.model_registry.get_chat_model(
    abi_module.configuration.abi_agent_model
)
```

When OpenAI's `gpt-5.1-mini` and OpenRouter's `openai/gpt-5.1-mini` are the
"same model" by two different provider ids, only the canonical id appears
in user-facing config; each provider module owns the mapping.

## The two registration calls

```python
registry.register(canonical_id, model)               # concrete entry
registry.register_chat_provider(provider, factory)   # generic factory
registry.register_embedding_provider(provider, factory)
```

**`register(canonical_id, model)`** — Adds a concrete `(canonical_id,
provider, Model)` entry. The `Model` object already carries its provider
name and provider-specific id. This is the path 99% of consumers care
about: the registered entry is what `get_chat_model("gpt-4.1-mini")`
returns.

**`register_chat_provider(provider, factory)`** — Registers a generic
`(provider_model_id) -> BaseChatModel` constructor for off-catalog
lookups. The api key is closed over in the factory. Only invoked when a
caller asks for a model id that *isn't* registered and pins
`provider=<this provider>`. Forward-compat escape hatch for "I want to
try OpenAI's `gpt-future-x` before someone adds a `ModelDefinition`
file for it" — never touched on normal catalog hits.

Same shape for `register_embedding_provider`.

## Auto-discovery via `ModelDefinition`

Provider modules don't call `register(...)` by hand. `BaseModule.on_load`
walks `<module_root>/models/*.py` (just like `ModuleAgentLoader` walks
`agents/*.py`) and registers every `ModelDefinition` subclass it finds.

The convention per file: one class per model.

```python
# naas_abi_marketplace/ai/chatgpt/models/gpt_4_1_mini.py
from langchain_openai import ChatOpenAI
from naas_abi_core.models.Model import (
    CanonicalModelId, ChatModel, ModelDefinition, ModelProvider,
)
from naas_abi_marketplace.ai.chatgpt import ABIModule
from pydantic import SecretStr


class Gpt41MiniModel(ModelDefinition):
    CANONICAL_ID = CanonicalModelId.GPT_4_1_MINI
    MODEL_ID     = "gpt-4.1-mini"
    PROVIDER     = ModelProvider.OPENAI

    model: ChatModel = ChatModel(
        model_id=MODEL_ID,
        provider=PROVIDER,
        model=ChatOpenAI(
            model=MODEL_ID,
            temperature=0,
            api_key=SecretStr(ABIModule.get_instance().configuration.openai_api_key),
        ),
    )


# Back-compat for code that still does ``from ... import model`` directly.
model: ChatModel = Gpt41MiniModel.model
```

Class-body evaluation happens at module-import time, which the loader
triggers inside `BaseModule.on_load` — after `__init__` has populated
`ABIModule._instances`, so `get_instance().configuration` is safe to call.

Files without a `ModelDefinition` subclass are silently skipped — useful
for helper modules or legacy duplicates that you want to keep importable
but not register.

## Lookup semantics

```python
registry.get_chat_model(canonical_id, provider=None)
registry.get_embedding_model(canonical_id, provider=None)
registry.get(canonical_id, provider=None)        # returns base Model
```

Resolution order:

1. **Provider-pinned exact match.** `(canonical_id, provider)` is in the
   registry → return that entry.
2. **Cross-provider fallback for the same canonical id.** Caller pinned
   `provider="openai"` but only `("claude-sonnet-4", "anthropic")` and
   `("claude-sonnet-4", "bedrock")` are registered → returns one of those
   (first registered wins). Lets you keep the same canonical id when one
   provider isn't configured.
3. **Off-catalog construction.** Canonical id isn't registered for *any*
   provider. The caller **must** have passed `provider=` — the registry
   uses that provider's chat/embedding factory with `canonical_id` as the
   provider-specific id. Raises `ModelNotFoundError` if no `provider=` or
   the provider has no factory.

Multiple registrations of the same `(canonical_id, provider)` are
allowed — auto-discovery can hit duplicate paths cleanly. First
registered wins on lookup. Direct `import` of a specific model file is
still the escape hatch when you need a precise variant.

## Defaults

The engine config carries two defaults:

```yaml
services:
  model_registry:
    default_chat_model: "gpt-4.1-mini"
    default_embedding_model: "text-embedding-3-large"
```

`Engine.load()` calls `registry.validate_defaults()` after every module's
`on_load` has run; it hard-fails if either configured default is not
registered. Catches typos and missing-module-enable mistakes at boot
instead of on first chat request.

`get_default_chat_model()` / `get_default_embedding_model()` resolve the
configured defaults at call time. These are what
`AbiAgent`, `OntologyEngineerAgent`, and the `IntentMapper`'s
None-fallback path call into.

## Process-wide accessor

The registry is intentionally a global catalog (unlike access-controlled
services like `triple_store` / `cache` / `secret` which stay behind
`EngineProxy` and the module dependency-declaration system). It's exposed
as a singleton in [`naas_abi_core/engine/context.py`](../../engine/context.py):

```python
from naas_abi_core.engine.context import get_default_model_registry

registry = get_default_model_registry()    # None if Engine.load() hasn't run
```

Used by `IntentMapper` and `chat_file_embeddings` so they can resolve
defaults from anywhere — agents, background threads, nexus app code —
without needing an engine handle. Bound by `Engine.load()` alongside the
EventService singleton.

For tests, use `with_model_registry_override(fake)` to swap in a fake
registry per context.

## Adding a new model to an existing provider module

1. Check if `CanonicalModelId` already has an entry; add one if not
   (`naas_abi_core/models/Model.py`). Canonical ids are pure
   convenience — the registry accepts raw strings too — but having
   them in the enum gives type-safe autocomplete to callers.
2. Drop a file at `<provider_module>/models/<short_name>.py` with one
   `ModelDefinition` subclass. The module's `on_load` will pick it up on
   the next boot — no `register(...)` call to update by hand.
3. (Optional) Keep a module-level `model = <Class>.model` alias if
   existing direct importers use `from ...models.foo import model`.

## Adding a new provider module

Outline of what a provider module's `__init__.py` does:

```python
class ABIModule(BaseModule):
    dependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService, ModelRegistryService],
    )

    class Configuration(ModuleConfiguration):
        my_provider_api_key: str

    def on_load(self):
        # BaseModule.on_load auto-registers everything under models/.
        super().on_load()

        # Register a chat-provider factory so off-catalog lookups work.
        api_key = SecretStr(self.configuration.my_provider_api_key)

        def chat_factory(provider_model_id: str) -> ChatMyProvider:
            return ChatMyProvider(model=provider_model_id, api_key=api_key)

        self.engine.services.model_registry.register_chat_provider(
            ModelProvider.MY_PROVIDER, chat_factory
        )

        # Same for embeddings if you ship one.
        def emb_factory(provider_model_id: str) -> MyProviderEmbeddings:
            return MyProviderEmbeddings(model=provider_model_id, api_key=api_key)

        self.engine.services.model_registry.register_embedding_provider(
            ModelProvider.MY_PROVIDER, emb_factory
        )
```

Then one `ModelDefinition` file per concrete model under `models/`. See
[`naas_abi_marketplace/ai/claude/__init__.py`](../../../../../naas-abi-marketplace/naas_abi_marketplace/ai/claude/__init__.py) for a complete reference.

## Common pitfalls

- **Class-body construction needs `ABIModule.get_instance()`.** Each
  `ModelDefinition` file calls `ABIModule.get_instance().configuration.*`
  at class-definition time. That only works once `BaseModule.__init__`
  has registered the module instance — which is guaranteed inside
  `BaseModule.on_load`, the only place auto-discovery imports model
  files. Direct `import` of a model file before module load will raise
  `Module ... not initialized`.
- **Configured default not registered → boot fails.** That's by design:
  `validate_defaults()` runs after all modules load. Either enable the
  provider module that ships your default, or change the config to a
  canonical id that *is* registered.
- **Off-catalog lookup with no provider= → `ModelNotFoundError`.** The
  registry refuses to guess which provider to route through. Either
  register the model (preferred) or pass `provider=` explicitly.
- **Two providers ship the same canonical id and you need to pin one** —
  use the call-site `provider=` argument (or the per-agent
  `abi_agent_provider` / `ontology_engineer_provider` config keys in
  `naas_abi`). Without a pin, the first-registered wins.
- **Embedding model is a `ChatModel` (or vice versa).** Registration goes
  into the same bucket; `get_chat_model` and `get_embedding_model` apply
  an `isinstance` check and raise if the type doesn't match. Use the
  right `ModelDefinition` (`ChatModel` vs `EmbeddingModel`) when you build
  the `model` attribute.

## Where to look

- [`ModelRegistryPort.py`](ModelRegistryPort.py) — `IModelRegistry` interface, errors, and factory type aliases.
- [`ModelRegistryService.py`](ModelRegistryService.py) — in-memory implementation.
- [`ModelRegistryFactory.py`](ModelRegistryFactory.py) — engine-side construction.
- [`ModelRegistryService_test.py`](ModelRegistryService_test.py) — full behaviour matrix.
- [`naas_abi_core/module/ModuleModelLoader.py`](../../module/ModuleModelLoader.py) — the auto-discovery loader.
- [`naas_abi_core/models/Model.py`](../../models/Model.py) — `Model` / `ChatModel` / `EmbeddingModel` / `ModelDefinition` / `CanonicalModelId` / `ModelProvider`.
- [`naas_abi_core/engine/context.py`](../../engine/context.py) — process-wide accessor.

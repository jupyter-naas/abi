# `ModelRegistryService`

## What it is
- An async service wrapper around `ModelRegistryClient` that resolves and lists models from the model registry.
- Returns portable `RemoteModel` wrappers built from registry `ModelDescriptor` results.

## Public API
- `class ModelRegistryService(client: ModelRegistryClient)`
  - Holds a registry client and exposes convenience async lookup/list methods.

### Methods
- `async get(canonical_id: str, provider: str | None = None) -> RemoteModel`
  - Resolve a model by canonical ID (and optional provider), with no specific kind.

- `async get_chat_model(canonical_id: str, provider: str | None = None) -> RemoteModel`
  - Resolve a chat model by canonical ID (and optional provider).

- `async get_embedding_model(canonical_id: str, provider: str | None = None) -> RemoteModel`
  - Resolve an embedding model by canonical ID (and optional provider).

- `async get_default_chat_model() -> RemoteModel`
  - Resolve the default chat model (empty canonical ID).

- `async get_default_embedding_model() -> RemoteModel`
  - Resolve the default embedding model (empty canonical ID).

- `async list_models() -> list[RemoteModel]`
  - List all models in the registry, returned as `RemoteModel` wrappers.

- `async list_canonical_ids() -> list[str]`
  - List unique canonical IDs from the registry model list, preserving first-seen order.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_sdk.model_registry.ModelRegistryClient` (must provide async `resolve(...)` and `list_models(...)`).
  - Protobuf types from `naas_abi_proto.model_registry.v1.model_registry_pb2`:
    - `ResolveRequest`, `ModelRef`, `ListModelsRequest`, `ModelDescriptor`.
  - `naas_abi_sdk.models.remote_model(...)` factory to build `RemoteModel` wrappers.

## Usage
```python
import asyncio

from naas_abi_sdk.model_registry import ModelRegistryClient
from naas_abi_sdk.services.model_registry import ModelRegistryService

async def main():
    client = ModelRegistryClient(...)  # construct per your SDK setup
    svc = ModelRegistryService(client)

    chat = await svc.get_chat_model("gpt-4o")
    models = await svc.list_models()
    ids = await svc.list_canonical_ids()

    print(chat, len(models), ids[:5])

asyncio.run(main())
```

## Caveats
- All lookup/list operations are `async` and require an event loop.
- `provider=None` is sent to the registry as an empty string.
- `list_canonical_ids()` derives IDs by calling `list_models()` and de-duplicates in order.

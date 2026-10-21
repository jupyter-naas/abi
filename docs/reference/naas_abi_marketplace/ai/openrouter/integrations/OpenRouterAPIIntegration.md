# OpenRouterAPIIntegration

## What it is
- A small integration client for the OpenRouter REST API.
- Wraps common endpoints (responses, analytics, credits, models, providers, keys).
- Adds filesystem caching for HTTP requests and optional JSON persistence to object storage via `StorageUtils`.

## Public API

### `OpenRouterAPIIntegrationConfiguration`
Dataclass configuration for the integration.
- `api_key: str` — OpenRouter API key (Bearer token).
- `object_storage: ObjectStorageService` — backing object storage used by `StorageUtils` for saving JSON files.
- `base_url: str = "https://openrouter.ai/api/v1"` — API base URL.
- `datastore_path: str = "openrouter"` — base path used when saving JSON snapshots.

### `OpenRouterAPIIntegration`
Main client class.

#### `create_response(input_prompt: str, tools: list[dict] | None = None, model: str = "openai/gpt-4.1-mini", temperature: float = 0.7, top_p: float = 0.9) -> dict`
- POST `/responses`
- Creates a response using the “Beta Responses” endpoint.
- Sends a payload with `input` (user message), optional `tools`, and generation parameters.

#### `get_user_activity(date: str | None = None) -> dict`
- GET `/activity`
- Returns user activity grouped by endpoint.
- Accepts optional `date` in `YYYY-MM-DD` (UTC, within last 30 days).

#### `get_remaining_credits() -> dict`
- GET `/credits`
- Returns remaining credits information.

#### `get_total_models_count() -> dict`
- GET `/models/count`
- Returns the total count of available models.

#### `list_models(params: dict | None = None, save_json: bool = True) -> list`
- GET `/models`
- Returns a flat list of models from the `data` field.
- If `save_json=True`, saves:
  - `openrouter/models/_all/models.json` (all models)
  - `openrouter/models/<provider>/models.json` (split by provider from model id prefix before `/`)

#### `get_model_parameters(author: str, slug: str) -> dict`
- GET `/parameters`
- Returns supported parameters and popularity information for a model.

#### `list_providers(save_json: bool = True) -> list`
- GET `/providers`
- Returns a list of providers from the `data` field.
- If `save_json=True`, saves `openrouter/providers/providers.json`.

#### `list_api_keys() -> dict`
- GET `/keys`
- Lists API keys.

#### `get_current_api_key() -> dict`
- GET `/key`
- Gets information for the current API key.

### `as_tools(configuration: OpenRouterAPIIntegrationConfiguration)`
- Returns a list of LangChain `StructuredTool` tools:
  - `openrouter_list_models` → calls `integration.list_models()`
  - `openrouter_list_providers` → calls `integration.list_providers()`
- Uses an empty Pydantic schema (`EmptySchema`) for tool arguments.

## Configuration/Dependencies
- Requires:
  - `requests`
  - `naas_abi_core`:
    - `Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`
    - `CacheFactory`, `DataType`
    - `ObjectStorageService`
    - `StorageUtils`
- Caching:
  - `_make_request` is cached via `CacheFactory.CacheFS_find_storage(subpath="openrouter")`
  - TTL: 1 day
  - Cache key: `"{method}_{endpoint}{params_as_k_v_concat}"` (body is not part of the cache key)
- Storage:
  - `object_storage` is used by `StorageUtils.save_json(...)` when `save_json=True`.

## Usage

```python
from naas_abi_marketplace.ai.openrouter.integrations.OpenRouterAPIIntegration import (
    OpenRouterAPIIntegration,
    OpenRouterAPIIntegrationConfiguration,
)

# You must provide an ObjectStorageService instance from naas_abi_core.
object_storage = ...  # ObjectStorageService

config = OpenRouterAPIIntegrationConfiguration(
    api_key="YOUR_OPENROUTER_API_KEY",
    object_storage=object_storage,
)

client = OpenRouterAPIIntegration(config)

credits = client.get_remaining_credits()
models = client.list_models(save_json=False)

resp = client.create_response("Say hello in one sentence.")
print(resp)
```

## Caveats
- `_make_request` caches responses based on method/endpoint/params only; different request bodies to the same endpoint with the same params can return cached results.
- `get_user_activity(date=None)` still sends `params={"date": None}`.
- `list_models` and `list_providers` optionally persist JSON to object storage; ensure `object_storage` is configured and accessible.
- Network/HTTP failures raise `IntegrationConnectionError`.

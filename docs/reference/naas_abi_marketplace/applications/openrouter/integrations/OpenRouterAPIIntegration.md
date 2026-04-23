# OpenRouterAPIIntegration

## What it is
- A small integration client for the **OpenRouter API**.
- Wraps several OpenRouter endpoints (models, providers, credits, analytics, beta responses).
- Includes:
  - Request handling with bearer auth
  - A 1-day filesystem cache for API requests
  - Optional JSON persistence of model lists to object storage (via `StorageUtils`)

## Public API

### `OpenRouterAPIIntegrationConfiguration`
Dataclass configuration for the integration.
- **Fields**
  - `api_key: str` — OpenRouter API key (Bearer token)
  - `object_storage: ObjectStorageService` — backing storage used by `StorageUtils` for JSON saving
  - `base_url: str = "https://openrouter.ai/api/v1"` — API base URL
  - `datastore_path: str = "openrouter"` — base path used when saving JSON (e.g., models)

### `OpenRouterAPIIntegration`
Integration client.

- `create_response(input_prompt: str, tools: Optional[list[Dict]] = None, model: str = "openai/gpt-4.1-mini", temperature: float = 0.7, top_p: float = 0.9) -> Dict`
  - POST `/responses`
  - Sends a beta “responses” payload with a single user message.
  - Accepts optional `tools` list.

- `get_user_activity(date: Optional[str] = None) -> Dict`
  - GET `/activity`
  - Query param: `date` (YYYY-MM-DD, last 30 days)

- `get_remaining_credits() -> Dict`
  - GET `/credits`

- `get_total_models_count() -> Dict`
  - GET `/models/count`

- `list_models(params: Optional[Dict] = None, save_json: bool = True) -> List`
  - GET `/models`
  - Returns the unwrapped list from `response["data"]` (or `[]`).
  - If `save_json=True`, saves:
    - All models to: `{datastore_path}/models/_all/models.json`
    - Models split by owner prefix (before `/` in model id) to: `{datastore_path}/models/{owner}/models.json`

- `get_model_parameters(author: str, slug: str) -> Dict`
  - GET `/parameters` with `author` and `slug` query params

- `list_providers() -> Dict`
  - GET `/providers`

- `list_api_keys() -> Dict`
  - GET `/keys`

- `get_current_api_key() -> Dict`
  - GET `/key`

### `as_tools(configuration: OpenRouterAPIIntegrationConfiguration)`
Builds LangChain tools from this integration.
- Returns a list of `langchain_core.tools.StructuredTool`:
  - `openrouter_list_models` → calls `integration.list_models()`
  - `openrouter_list_providers` → calls `integration.list_providers()`

## Configuration/Dependencies
- **HTTP**: `requests`
- **Core integration types**: `naas_abi_core.integration.integration`
  - Uses `IntegrationConnectionError` on request failures.
- **Caching**:
  - Uses `CacheFactory.CacheFS_find_storage(subpath="openrouter")`
  - `_make_request` is cached for **1 day** with cache key based on method/endpoint/params.
- **Object storage**:
  - `object_storage: ObjectStorageService` is required by configuration.
  - Used by `StorageUtils.save_json(...)` when `list_models(save_json=True)`.

## Usage

```python
from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import (
    OpenRouterAPIIntegration,
    OpenRouterAPIIntegrationConfiguration,
)

# Provide a concrete ObjectStorageService implementation from your environment
object_storage = ...  # ObjectStorageService

config = OpenRouterAPIIntegrationConfiguration(
    api_key="YOUR_OPENROUTER_API_KEY",
    object_storage=object_storage,
)

client = OpenRouterAPIIntegration(config)

# Models
models = client.list_models(save_json=False)
print(len(models))

# Providers
providers = client.list_providers()
print(providers)

# Credits
credits = client.get_remaining_credits()
print(credits)

# Beta responses
resp = client.create_response("Say hello in one sentence.")
print(resp)
```

## Caveats
- `_make_request` caches responses for 1 day; repeated calls with the same method/endpoint/params may return cached data.
- `list_models(save_json=True)` writes JSON via `StorageUtils` to paths derived from `datastore_path`; ensure `object_storage` is correctly configured.
- Cache key uses only `method`, `endpoint`, and `params` (not request body); POST calls with different payloads but same endpoint may collide in cache.

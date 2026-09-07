# OpenRouterAPIIntegration

## What it is
- A small Python integration client for the **OpenRouter API** (`https://openrouter.ai/api/v1`).
- Provides typed configuration plus convenience methods for:
  - Models, model parameters
  - Providers
  - Credits and activity analytics
  - API key endpoints
  - Beta `/responses` endpoint
- Includes:
  - Bearer-token auth via `Authorization: Bearer ...`
  - Filesystem-backed caching of requests for **1 day**
  - Optional JSON persistence of model lists to object storage via `StorageUtils`

## Public API

### `OpenRouterAPIIntegrationConfiguration`
Dataclass extending `IntegrationConfiguration`.

- **Fields**
  - `api_key: str` — OpenRouter API key (used as Bearer token)
  - `object_storage: ObjectStorageService` — used by `StorageUtils` for JSON persistence
  - `base_url: str = "https://openrouter.ai/api/v1"` — API base URL
  - `datastore_path: str = "openrouter"` — base path for saved JSON artifacts

### `OpenRouterAPIIntegration`
Client extending `Integration`.

- `create_response(input_prompt: str, tools: list[dict] | None = None, model: str = "openai/gpt-4.1-mini", temperature: float = 0.7, top_p: float = 0.9) -> dict`
  - `POST /responses`
  - Sends a payload with a single user message in `input`, plus optional `tools`.

- `get_user_activity(date: str | None = None) -> dict`
  - `GET /activity`
  - Always passes `params={"date": date}` (even if `date` is `None`).

- `get_remaining_credits() -> dict`
  - `GET /credits`

- `get_total_models_count() -> dict`
  - `GET /models/count`

- `list_models(params: dict | None = None, save_json: bool = True) -> list`
  - `GET /models`
  - Returns `response["data"]` (or `[]`).
  - If `save_json=True`, saves:
    - All models: `{datastore_path}/models/_all/models.json`
    - Models grouped by owner (prefix before `/` in `model["id"]`, otherwise `"unknown"`):
      `{datastore_path}/models/{owner}/models.json`

- `get_model_parameters(author: str, slug: str) -> dict`
  - `GET /parameters` with query params `author` and `slug`

- `list_providers() -> dict`
  - `GET /providers`

- `list_api_keys() -> dict`
  - `GET /keys`

- `get_current_api_key() -> dict`
  - `GET /key`

> Note: `_make_request(...)` is an internal method but is central to behavior; it performs the HTTP call and raises `IntegrationConnectionError` on request errors.

### `as_tools(configuration: OpenRouterAPIIntegrationConfiguration) -> list`
- Builds two LangChain `StructuredTool` tools backed by an internal `OpenRouterAPIIntegration` instance:
  - `openrouter_list_models` → `integration.list_models()`
  - `openrouter_list_providers` → `integration.list_providers()`
- Uses an empty Pydantic schema (`EmptySchema`) for arguments.

## Configuration/Dependencies
- **HTTP**: `requests`
- **Core integration types** (exceptions/base classes):
  - `Integration`, `IntegrationConfiguration`, `IntegrationConnectionError` from `naas_abi_core.integration.integration`
- **Caching**:
  - `CacheFactory.CacheFS_find_storage(subpath="openrouter")`
  - `_make_request` is cached for **1 day** (`ttl=datetime.timedelta(days=1)`) as `DataType.JSON`
- **Object storage**:
  - `ObjectStorageService` required in configuration
  - `StorageUtils(configuration.object_storage)` used for `save_json(...)` in `list_models`

## Usage

```python
from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import (
    OpenRouterAPIIntegration,
    OpenRouterAPIIntegrationConfiguration,
)

object_storage = ...  # Provide an ObjectStorageService from your environment

cfg = OpenRouterAPIIntegrationConfiguration(
    api_key="YOUR_OPENROUTER_API_KEY",
    object_storage=object_storage,
)

client = OpenRouterAPIIntegration(cfg)

models = client.list_models(save_json=False)
print("models:", len(models))

providers = client.list_providers()
print("providers keys:", providers.keys() if isinstance(providers, dict) else type(providers))

credits = client.get_remaining_credits()
print("credits:", credits)

resp = client.create_response("Say hello in one sentence.")
print("response:", resp)
```

## Caveats
- **Request caching (1 day)**: `_make_request` is cached by a key built from `method`, `endpoint`, and `params` only.
  - The cache key does **not** include the request body (`data`), so different POST payloads to the same endpoint with the same params may collide.
- **`get_user_activity` params**: passes `{"date": None}` when no date is provided; behavior depends on the server’s handling of that query parameter.
- **Model JSON persistence**: `list_models(save_json=True)` writes JSON to paths derived from `datastore_path`; ensure `object_storage` is configured and writable.

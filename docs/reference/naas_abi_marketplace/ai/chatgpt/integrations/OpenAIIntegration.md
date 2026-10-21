# OpenAIIntegration

## What it is
- A small wrapper around the `openai` Python client (`OpenAI`) for:
  - Listing models and retrieving model metadata.
  - Creating chat completions.
  - Caching results to filesystem (1-day TTL).
  - Persisting JSON outputs to a configured datastore via `StorageUtils` + `ObjectStorageService`.
  - Exposing the integration as LangChain `StructuredTool` tools via `as_tools()`.

## Public API

### `OpenAIIntegrationConfiguration` (dataclass)
Configuration for `OpenAIIntegration`.
- `api_key: str` — OpenAI API key.
- `datastore_path: str` — Base path used to build output directories for saved JSON.
- `object_storage: ObjectStorageService` — Storage backend used by `StorageUtils`.

### `OpenAIIntegration`
Integration class.

- `__init__(configuration: OpenAIIntegrationConfiguration)`
  - Creates an `OpenAI(api_key=...)` client.
  - Initializes `StorageUtils` with the provided `object_storage`.

- `list_models() -> dict`
  - Calls `self.__openai.models.list()`.
  - Saves JSON to: `{datastore_path}/models/_all/models.json`
  - Returns: `{"models": [<model dict>, ...]}`.
  - Cached (filesystem) for 1 day.

- `retrieve_model(model_id: str) -> dict`
  - Calls `self.__openai.models.retrieve(model_id)`.
  - Saves JSON to: `{datastore_path}/models/{model_id}/{model_id}_info.json`
  - Returns: `<model dict>`.
  - Cached (filesystem) for 1 day.

- `create_chat_completion(prompt: str | None = None, system_prompt: str = "You are a helpful assistant.", messages: list[dict[str, str]] | None = None, model: str = "o3-mini", temperature: float = 0.3) -> dict`
  - If `messages is None`, it becomes `[]`.
  - If `messages` is empty and `prompt` is provided, builds:
    - `{"role": "developer", "content": system_prompt}`
    - `{"role": "user", "content": prompt}`
  - Calls `self.__openai.chat.completions.create(...)`:
    - If `model.startswith("o")`: does **not** pass `temperature`.
    - Else: passes `temperature`.
  - If a first choice message content is present:
    - Saves JSON to: `{datastore_path}/completions/{model}/{model}_{temperature}.json`
    - Returns: `{"content": <message content>}`
  - Otherwise returns `{}`.
  - Cached (filesystem) for 1 day (cache key includes `prompt`, `system_prompt`, `messages`, `model`, `temperature`).

### `as_tools(configuration: OpenAIIntegrationConfiguration) -> list[StructuredTool]`
Creates a new `OpenAIIntegration` and returns LangChain tools:
- `openai_list_models` — calls `list_models()`
- `openai_retrieve_model` — calls `retrieve_model(model_id=...)`
- `openai_create_chat_completion` — calls `create_chat_completion(prompt=..., system_prompt=..., model=..., temperature=...)`

## Configuration/Dependencies
- External libraries:
  - `openai` (`OpenAI`)
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (tool argument schemas)
- `naas_abi_core`:
  - `Integration`, `IntegrationConfiguration`
  - `CacheFactory` + `DataType` (decorator-based caching)
  - `ObjectStorageService`, `StorageUtils` (JSON persistence)
- Cache:
  - Uses `CacheFactory.CacheFS_find_storage(subpath="openai")`
  - All cached methods use `DataType.PICKLE` and `ttl=timedelta(days=1)`

## Usage

```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIIntegration import (
    OpenAIIntegration,
    OpenAIIntegrationConfiguration,
)

object_storage = ObjectStorageService(...)  # provide your implementation/config

cfg = OpenAIIntegrationConfiguration(
    api_key="YOUR_OPENAI_API_KEY",
    datastore_path="/tmp/naas/openai",
    object_storage=object_storage,
)

openai_integration = OpenAIIntegration(cfg)

print(openai_integration.list_models())
print(openai_integration.retrieve_model("gpt-4.1-mini"))
print(
    openai_integration.create_chat_completion(
        prompt="Write a haiku about caching.",
        system_prompt="You are a concise assistant.",
        model="o3-mini",
        temperature=0.3,
    )
)
```

Using LangChain tools:

```python
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIIntegration import as_tools

tools = as_tools(cfg)
# tools is a list of StructuredTool
```

## Caveats
- `create_chat_completion` only persists/returns content when the response contains `choices[0].message.content`; otherwise it returns `{}`.
- For models whose name starts with `"o"`, `temperature` is not passed to the OpenAI API call (but is still used in cache key and output filename).
- The cache key for `create_chat_completion` stringifies `messages`; large inputs may create large cache keys.

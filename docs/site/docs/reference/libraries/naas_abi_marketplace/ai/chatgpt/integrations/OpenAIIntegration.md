# OpenAIIntegration

## What it is
- A small integration wrapper around the `openai` Python client.
- Adds:
  - Filesystem caching (1 day TTL) for API calls.
  - JSON persistence of retrieved models and chat completions to a configured datastore via `StorageUtils` and an `ObjectStorageService`.
  - Optional conversion into LangChain `StructuredTool` tools via `as_tools()`.

## Public API

### `OpenAIIntegrationConfiguration`
Dataclass configuration for the integration.
- Fields:
  - `api_key: str` — OpenAI API key.
  - `datastore_path: str` — Base path used to build output directories for saved JSON.
  - `object_storage: ObjectStorageService` — Storage backend used by `StorageUtils`.

### `OpenAIIntegration`
Integration class for OpenAI endpoints.

- `list_models() -> Dict`
  - Calls `client.models.list()`.
  - Saves `models.json` under: `{datastore_path}/models/_all/models.json`.
  - Returns: `{"models": [ ...model dicts... ]}`.
  - Cached for 1 day.

- `retrieve_model(model_id: str) -> Dict`
  - Calls `client.models.retrieve(model_id)`.
  - Saves `{model_id}_info.json` under: `{datastore_path}/models/{model_id}/`.
  - Returns: model dict.
  - Cached for 1 day.

- `create_chat_completion(prompt: Optional[str] = None, system_prompt: str = "You are a helpful assistant.", messages: List[Dict[str, str]] = [], model: str = "o3-mini", temperature: float = 0.3) -> Dict`
  - Calls `client.chat.completions.create(...)`.
  - If `messages` is empty and `prompt` is provided, constructs messages:
    - `{"role": "developer", "content": system_prompt}`
    - `{"role": "user", "content": prompt}`
  - If `model` starts with `"o"`, it does **not** pass `temperature`; otherwise it does.
  - On success, saves the completion JSON under:
    - `{datastore_path}/completions/{model}/{model}_{temperature}.json`
  - Returns: `{"content": <first choice message content>}` or `{}` if content is unavailable.
  - Cached for 1 day.

### `as_tools(configuration: OpenAIIntegrationConfiguration) -> List[StructuredTool]`
Converts the integration into LangChain tools:
- `openai_list_models`
- `openai_retrieve_model` (args: `model_id`)
- `openai_create_chat_completion` (args: `prompt`, `system_prompt`, `model`, `temperature`)

## Configuration/Dependencies
- External dependencies:
  - `openai` (`OpenAI` client)
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (tool argument schemas)
  - `naas_abi_core`:
    - `Integration`, `IntegrationConfiguration`
    - `CacheFactory` + `DataType` (filesystem cache)
    - `ObjectStorageService`, `StorageUtils` (JSON persistence)
- Caching:
  - Uses `CacheFactory.CacheFS_find_storage(subpath="openai")`.
  - All decorated methods have a TTL of 1 day and cache as `DataType.PICKLE`.

## Usage

```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIIntegration import (
    OpenAIIntegration,
    OpenAIIntegrationConfiguration,
)

# You must provide an ObjectStorageService instance appropriate for your environment.
object_storage = ObjectStorageService(...)  # implementation-specific

cfg = OpenAIIntegrationConfiguration(
    api_key="YOUR_OPENAI_API_KEY",
    datastore_path="/tmp/naas/openai",
    object_storage=object_storage,
)

client = OpenAIIntegration(cfg)

# List models (cached; also writes models.json)
models = client.list_models()

# Retrieve one model (cached; also writes {model_id}_info.json)
model_info = client.retrieve_model("gpt-4.1-mini")

# Create a chat completion (cached; also writes completion JSON)
resp = client.create_chat_completion(
    prompt="Write a haiku about caching.",
    system_prompt="You are a concise assistant.",
    model="o3-mini",
    temperature=0.3,
)
print(resp.get("content"))
```

Using as LangChain tools:

```python
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIIntegration import as_tools, OpenAIIntegrationConfiguration

tools = as_tools(cfg)
# tools is a list of StructuredTool objects usable in LangChain.
```

## Caveats
- `messages` default is a mutable list (`[]`); if mutated externally it could affect subsequent calls.
- The cache key for `create_chat_completion` includes `messages` and prompts stringified; large/complex inputs may produce unwieldy keys.
- For models whose name starts with `"o"`, `temperature` is not passed to the OpenAI API call (but is still used in cache key and filename).

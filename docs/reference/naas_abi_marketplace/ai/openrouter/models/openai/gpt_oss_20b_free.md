# GptOss20bFreeModel

## What it is
- A model definition that configures a LangChain `ChatOpenAI` client to call OpenRouter’s **`openai/gpt-oss-20b:free`** chat model.
- Exposes a prebuilt `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- **`OPENROUTER_BASE_URL: str`**
  - Constant base URL for OpenRouter API: `https://openrouter.ai/api/v1`.

- **`class GptOss20bFreeModel(ModelDefinition)`**
  - Model definition wrapper with static identifiers and an embedded `ChatModel`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_OSS_20B_FREE`
    - `MODEL_ID`: `"openai/gpt-oss-20b:free"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: configured chat model instance

- **`model: ChatModel`**
  - Module-level alias for `GptOss20bFreeModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
  - Uses OpenRouter base URL via `base_url=OPENROUTER_BASE_URL`.

- **Client settings (hardcoded)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `context_window=131072`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_oss_20b_free import model

# Access the underlying LangChain chat client
llm = model.model

# Example call shape depends on your LangChain version.
# Typically, you can invoke with a list of messages.
response = llm.invoke("Hello!")  # or llm.invoke([{"role": "user", "content": "Hello!"}])
print(response)
```

## Caveats
- The API key is sourced from `ABIModule` configuration at import time; missing/invalid configuration will break instantiation.
- Network behavior (timeouts/retries) is fixed to `timeout=120` and `max_retries=3` in this definition.

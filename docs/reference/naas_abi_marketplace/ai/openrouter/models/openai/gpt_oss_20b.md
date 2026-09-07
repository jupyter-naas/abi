# GptOss20bModel

## What it is
- Defines an OpenRouter-backed chat model configuration for **`openai/gpt-oss-20b`** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, etc.).

## Public API
- **`class GptOss20bModel(ModelDefinition)`**
  - **`CANONICAL_ID`**: `CanonicalModelId.GPT_OSS_20B`
  - **`MODEL_ID`**: `"openai/gpt-oss-20b"`
  - **`PROVIDER`**: `ModelProvider.OPENROUTER`
  - **`model: ChatModel`**: Preconfigured `ChatModel` wrapping a `ChatOpenAI` client:
    - `temperature=0`, `timeout=120`, `max_retries=3`
    - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
    - `base_url="https://openrouter.ai/api/v1"`
    - `context_window=131072`
    - Includes descriptive metadata (name, owner, description, pricing, supported parameters, etc.)
- **`model: ChatModel`** (module-level)
  - Alias to `GptOss20bModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to authenticate to OpenRouter).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_oss_20b import model

# Access the underlying LangChain chat client
llm = model.model

# Example call (LangChain v0.1+ style)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- The OpenRouter API key is retrieved at import time via `ABIModule.get_instance().configuration.openrouter_api_key`; missing/invalid configuration may cause failures when constructing or using the client.
- The configured base URL is fixed to `https://openrouter.ai/api/v1`.

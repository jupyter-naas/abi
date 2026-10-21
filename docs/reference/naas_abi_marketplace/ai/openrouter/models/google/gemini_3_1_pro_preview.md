# Gemini31ProPreviewModel

## What it is
- Defines a LangChain `ChatOpenAI` chat model configuration for the OpenRouter-hosted model **`google/gemini-3.1-pro-preview`**.
- Exposes a ready-to-use `ChatModel` instance as `model`.

## Public API
- **`Gemini31ProPreviewModel`** (`ModelDefinition`)
  - **Class constants**
    - `CANONICAL_ID`: `CanonicalModelId.GEMINI_3_1_PRO_PREVIEW`
    - `MODEL_ID`: `"google/gemini-3.1-pro-preview"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Attributes**
    - `model: ChatModel` — A configured chat model:
      - Underlying client: `langchain_openai.ChatOpenAI`
      - Parameters: `temperature=0`, `timeout=120`, `max_retries=3`
      - OpenRouter base URL: `https://openrouter.ai/api/v1`
      - API key sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
- **Module-level `model: ChatModel`**
  - Alias to `Gemini31ProPreviewModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set (used as the OpenRouter API key).
- **Endpoint**
  - Uses OpenRouter API base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.google.gemini_3_1_pro_preview import model

# `model.model` is the underlying LangChain ChatOpenAI instance
response = model.model.invoke("Hello! What model are you?")
print(response)
```

## Caveats
- Importing this module initializes `ChatOpenAI` immediately and reads the OpenRouter API key from `ABIModule` configuration at import time.

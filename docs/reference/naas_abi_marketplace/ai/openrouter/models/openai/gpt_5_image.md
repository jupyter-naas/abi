# Gpt5ImageModel

## What it is
- A model definition that registers the **OpenRouter** hosted **`openai/gpt-5-image`** chat model using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance configured with OpenRouter’s base URL and an API key sourced from `ABIModule` configuration.

## Public API
- `class Gpt5ImageModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5_IMAGE`
  - `MODEL_ID`: `"openai/gpt-5-image"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Preconfigured `ChatModel` wrapping a `ChatOpenAI` client:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key)`
    - Includes metadata (context window, pricing, architecture, supported/default parameters, etc.)

- `model: ChatModel`
  - Alias to `Gpt5ImageModel.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (OpenRouter API key).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_image import model

# Access the underlying LangChain chat model client
llm = model.model  # ChatOpenAI instance

# Example call (requires valid OpenRouter API key configured in ABIModule)
result = llm.invoke("Describe an image of a red cat wearing sunglasses.")
print(result)
```

## Caveats
- API key is pulled from `ABIModule` at import time; missing/invalid configuration will fail when constructing the `ChatOpenAI` client.
- The module defines configuration for a multimodal model (`text+image+file->text+image`), but this file does not provide helper utilities for packaging image/file inputs; you must use the underlying client’s supported message format.

# Gpt5ImageMiniModel

## What it is
- A `ModelDefinition` that registers the **OpenRouter**-hosted **OpenAI `openai/gpt-5-image-mini`** model as a `ChatModel`.
- Wraps a `langchain_openai.ChatOpenAI` client preconfigured for OpenRouter (`https://openrouter.ai/api/v1`).

## Public API
- **`OPENROUTER_BASE_URL: str`**
  - Base URL for OpenRouter API (`https://openrouter.ai/api/v1`).

- **`class Gpt5ImageMiniModel(ModelDefinition)`**
  - Defines a single static model entry:
    - `CANONICAL_ID = CanonicalModelId.GPT_5_IMAGE_MINI`
    - `MODEL_ID = "openai/gpt-5-image-mini"`
    - `PROVIDER = ModelProvider.OPENROUTER`
    - `model: ChatModel` – prebuilt `ChatModel` containing:
      - `model=ChatOpenAI(...)` configured with `temperature=0`, `timeout=120`, `max_retries=3`, `base_url=OPENROUTER_BASE_URL`
      - `api_key` loaded from `ABIModule.get_instance().configuration.openrouter_api_key` (wrapped in `pydantic.SecretStr`)
      - metadata (context window, pricing, architecture, etc.)

- **`model: ChatModel`**
  - Module-level alias to `Gpt5ImageMiniModel.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (for configuration lookup)
  - `pydantic.SecretStr`

- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (OpenRouter API key).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_image_mini import model

# LangChain chat model client (ChatOpenAI) is stored in model.model
llm = model.model

# Example invocation (depending on your LangChain version)
result = llm.invoke("Hello from GPT-5 Image Mini")
print(result)
```

## Caveats
- The API key is pulled at import time via `ABIModule.get_instance().configuration.openrouter_api_key`; missing/invalid configuration can cause runtime failures when constructing the client.

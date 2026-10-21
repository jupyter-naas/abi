# Mixtral8x22bInstructModel

## What it is
- A `ModelDefinition` that registers the **Mixtral 8x22B Instruct** chat model for the **OpenRouter** provider.
- Exposes a preconfigured `ChatModel` backed by `langchain_openai.ChatOpenAI` and OpenRouter’s API base URL.

## Public API
- `class Mixtral8x22bInstructModel(ModelDefinition)`
  - Purpose: Defines metadata and the instantiated `ChatModel` for `mistralai/mixtral-8x22b-instruct`.
  - Key class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.MIXTRAL_8X22B_INSTRUCT`
    - `MODEL_ID`: `"mistralai/mixtral-8x22b-instruct"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Field:
    - `model: ChatModel`: The configured chat model instance (includes context window, pricing, supported parameters, etc.).
- `model: ChatModel`
  - Purpose: Module-level alias to `Mixtral8x22bInstructModel.model` for convenient importing.

## Configuration/Dependencies
- External dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration required:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set; it is used to build `ChatOpenAI(api_key=SecretStr(...))`.
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- `ChatOpenAI` is instantiated with:
  - `model="mistralai/mixtral-8x22b-instruct"`, `temperature=0`, `timeout=120`, `max_retries=3`, `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mixtral_8x22b_instruct import model

# Access the underlying LangChain chat model
llm = model.model

# Example call (LangChain ChatOpenAI interface)
result = llm.invoke("Write a one-line haiku about documentation.")
print(result)
```

## Caveats
- The OpenRouter API key is fetched at import time via `ABIModule.get_instance().configuration.openrouter_api_key`; missing/misconfigured credentials can cause failures during initialization.

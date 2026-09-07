# MistralLarge2407Model

## What it is
- Defines the **Mistral Large 2407** chat model for the **OpenRouter** provider.
- Exposes a preconfigured `ChatModel` wrapping `langchain_openai.ChatOpenAI` with OpenRouter base URL and API key sourced from `ABIModule` configuration.

## Public API
- `class MistralLarge2407Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_LARGE_2407`
  - `MODEL_ID`: `"mistralai/mistral-large-2407"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully constructed chat model definition (includes metadata like context window, pricing, supported parameters, etc.).
- Module-level export:
  - `model: ChatModel`: Alias to `MistralLarge2407Model.model` for convenient imports.

## Configuration/Dependencies
- **Depends on**:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` (singleton config access)
  - `pydantic.SecretStr`
- **Configuration required**:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set.
- **OpenRouter endpoint**:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_large_2407 import model

# Access the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call (LangChain API)
response = llm.invoke("Hello! Summarize Mistral Large 2407 in one sentence.")
print(response)
```

## Caveats
- Importing the module constructs `ChatOpenAI` immediately and reads the OpenRouter API key from `ABIModule` configuration; missing/invalid configuration can fail at import time.
- The `ChatOpenAI` instance is configured with:
  - `temperature=0`, `timeout=120`, `max_retries=3`, `base_url` set to OpenRouter.

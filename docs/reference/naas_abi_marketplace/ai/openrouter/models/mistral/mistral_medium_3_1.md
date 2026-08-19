# MistralMedium31Model

## What it is
- A model definition that wires the **Mistral Medium 3.1** chat model through **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a preconfigured `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class MistralMedium31Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_MEDIUM_3_1`
  - `MODEL_ID`: `"mistralai/mistral-medium-3.1"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model wrapper containing:
    - `model`: `ChatOpenAI(...)` client configured for OpenRouter
    - `context_window`: `131072`
    - Various metadata fields (name, owner, pricing, supported/default parameters, etc.)
- `model: ChatModel`
  - Module-level alias to `MistralMedium31Model.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`
- Requires OpenRouter API key read from:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- Uses OpenRouter base URL:
  - `https://openrouter.ai/api/v1`
- `ChatOpenAI` is instantiated with:
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`
  - `api_key=SecretStr(...)`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_medium_3_1 import model

# `model.model` is the underlying ChatOpenAI client (LangChain)
client = model.model

# Example call (method name depends on your LangChain version)
result = client.invoke("Hello from Mistral Medium 3.1")
print(result)
```

## Caveats
- The OpenRouter API key must be available via `ABIModule` configuration at import time, because the `ChatOpenAI` client is constructed during module import.

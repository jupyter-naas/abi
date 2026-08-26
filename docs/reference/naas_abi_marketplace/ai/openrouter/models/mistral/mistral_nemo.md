# MistralNemoModel

## What it is
- A model definition that wires the **Mistral Nemo** chat model (`mistralai/mistral-nemo`) through **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance as `model`.

## Public API
- `class MistralNemoModel(ModelDefinition)`
  - Purpose: Defines metadata and a configured `ChatModel` for the Mistral Nemo model on OpenRouter.
  - Key class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_NEMO`
    - `MODEL_ID`: `"mistralai/mistral-nemo"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Field:
    - `model: ChatModel`: A configured `ChatModel` wrapping `ChatOpenAI` with OpenRouter base URL.
- `model: ChatModel`
  - Purpose: Module-level alias to `MistralNemoModel.model` for convenience.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
- **Endpoint**
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`
- **Client defaults (as configured here)**
  - `temperature=0`, `timeout=120`, `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_nemo import model

# Access the underlying LangChain chat client
llm = model.model

# Typical LangChain usage (exact methods depend on your LangChain version)
result = llm.invoke("Write a one-sentence summary of Mistral Nemo.")
print(result)
```

## Caveats
- This module depends on `ABIModule` being initialized and providing a valid `openrouter_api_key`; otherwise model creation may fail at import time.

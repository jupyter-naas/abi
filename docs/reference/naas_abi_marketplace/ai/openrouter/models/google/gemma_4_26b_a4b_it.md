# `Gemma426BA4BItModel`

## What it is
- A model definition that wires the OpenRouter-hosted **`google/gemma-4-26b-a4b-it`** chat model into the project via `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance configured with OpenRouter base URL and API key from `ABIModule` configuration.

## Public API
- **`class Gemma426BA4BItModel(ModelDefinition)`**
  - Purpose: Defines metadata and a preconfigured `ChatModel` for `google/gemma-4-26b-a4b-it`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GEMMA_4_26B_A4B_IT`
    - `MODEL_ID`: `"google/gemma-4-26b-a4b-it"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` wrapping a `ChatOpenAI` client configured for OpenRouter.
- **`model: ChatModel`**
  - Purpose: Module-level alias to `Gemma426BA4BItModel.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`
- **Client settings (hardcoded)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.google.gemma_4_26b_a4b_it import model

# `model.model` is the underlying LangChain ChatOpenAI instance.
llm = model.model

# Example call (method availability depends on your LangChain version)
response = llm.invoke("Hello!")
print(response)
```

## Caveats
- Requires `ABIModule` to be initialized and `openrouter_api_key` to be set; otherwise model construction/access may fail at import time.
- This module only defines configuration; it does not implement higher-level prompting, tool schemas, or agent logic.

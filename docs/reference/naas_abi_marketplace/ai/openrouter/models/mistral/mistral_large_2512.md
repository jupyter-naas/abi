# MistralLarge2512Model

## What it is
- Defines an OpenRouter-backed LangChain chat model configuration for **`mistralai/mistral-large-2512`**.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured with:
  - `langchain_openai.ChatOpenAI`
  - OpenRouter base URL (`https://openrouter.ai/api/v1`)
  - API key sourced from `ABIModule` configuration.

## Public API
- **`class MistralLarge2512Model(ModelDefinition)`**
  - **Purpose:** Holds metadata and a preconfigured `ChatModel` for the Mistral Large 3 2512 model on OpenRouter.
  - **Class attributes:**
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_LARGE_2512`
    - `MODEL_ID`: `"mistralai/mistral-large-2512"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - **Fields:**
    - `model: ChatModel` — the configured chat model wrapper (includes LangChain `ChatOpenAI` instance and model metadata).
- **`model: ChatModel`**
  - **Purpose:** Module-level alias to `MistralLarge2512Model.model` for convenient import/use.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
- **Runtime settings (as configured)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url="https://openrouter.ai/api/v1"`
  - `context_window=262144`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_large_2512 import model

# Access the underlying LangChain ChatOpenAI client:
llm = model.model  # ChatOpenAI instance

# Example call (LangChain supports invoke with a string for chat models):
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- The OpenRouter API key must be available via `ABIModule` configuration at import time, since the `ChatOpenAI` instance is constructed during module import/class definition.

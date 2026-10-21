# `MistralSmall2603Model`

## What it is
- A model definition that configures **Mistral Small 4 (2603)** for use via **OpenRouter** using `langchain_openai.ChatOpenAI`.
- Exposes a pre-built `ChatModel` instance (`model`) ready to be used by the surrounding Naas ABI framework.

## Public API
- `class MistralSmall2603Model(ModelDefinition)`
  - Purpose: Defines metadata and a configured `ChatModel` for the OpenRouter-hosted model.
  - Public class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.MISTRAL_SMALL_2603`
    - `MODEL_ID`: `"mistralai/mistral-small-2603"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Public instance attribute:
    - `model: ChatModel`: A `ChatModel` wrapping a `ChatOpenAI` client plus model metadata (context window, pricing, supported parameters, etc.).

- `model: ChatModel`
  - Purpose: Module-level alias to `MistralSmall2603Model.model` for convenient importing.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- Runtime configuration:
  - Uses `ABIModule.get_instance().configuration.openrouter_api_key` as the OpenRouter API key.
  - OpenRouter base URL is fixed to: `https://openrouter.ai/api/v1`

- `ChatOpenAI` client configuration in this module:
  - `model="mistralai/mistral-small-2603"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url="https://openrouter.ai/api/v1"`
  - `api_key=SecretStr(<openrouter_api_key>)`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.mistral.mistral_small_2603 import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Then use it as you would a ChatOpenAI instance (method availability depends on your LangChain version)
# Example (commonly supported in LangChain):
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized/configured so `configuration.openrouter_api_key` is available; otherwise model construction may fail at import time.
- The module constructs the `ChatOpenAI` client eagerly at import time (API key must be present during import).

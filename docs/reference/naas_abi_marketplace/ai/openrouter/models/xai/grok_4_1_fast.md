# Grok41FastModel

## What it is
- Defines a LangChain `ChatOpenAI` chat model configuration for OpenRouter’s `x-ai/grok-4.1-fast`.
- Exposes a ready-to-use `ChatModel` instance (`model`) for the marketplace runtime.

## Public API
- `class Grok41FastModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GROK_4_1_FAST`
  - `MODEL_ID`: `"x-ai/grok-4.1-fast"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured `ChatModel` wrapping `ChatOpenAI`:
    - `temperature=0`
    - `timeout=120`
    - `max_retries=3`
    - `base_url="https://openrouter.ai/api/v1"`
    - `api_key` read from `ABIModule.get_instance().configuration.openrouter_api_key` (wrapped in `pydantic.SecretStr`)
- `model: ChatModel`
  - Module-level alias to `Grok41FastModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for retrieving `openrouter_api_key`
  - `pydantic.SecretStr`
- Requires OpenRouter API key available via:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- Uses OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.xai.grok_4_1_fast import model

# Access the underlying LangChain ChatOpenAI instance if needed
llm = model.model
```

## Caveats
- Importing this module initializes the `ChatOpenAI` client immediately and reads the OpenRouter API key from `ABIModule` at import time.

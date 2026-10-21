# Gpt4oModel

## What it is
- Defines the **GPT-4o** chat model configuration for the **OpenRouter** provider.
- Exposes a ready-to-use `ChatModel` instance backed by `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt4oModel(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_4O`
    - `MODEL_ID`: `"openai/gpt-4o"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Preconfigured `ChatModel` wrapping `ChatOpenAI` with:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` from `ABIModule.get_instance().configuration.openrouter_api_key`
    - Metadata includes context window, pricing, supported parameters, etc.

- `model: ChatModel`
  - Module-level alias to `Gpt4oModel.model`.

## Configuration/Dependencies
- External dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types (`ChatModel`, `ModelDefinition`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be available (used to authenticate to OpenRouter).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4o import model

# Access the underlying LangChain chat model
llm = model.model

# Example call (method names depend on your LangChain version)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- The module pulls the API key at import time via `ABIModule.get_instance()`. Ensure the OpenRouter configuration is initialized before importing this module.
- This file only configures the model; it does not implement higher-level prompting or tool logic.

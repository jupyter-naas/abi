# O3MiniHighModel

## What it is
- Defines a `ModelDefinition` for the OpenRouter-hosted OpenAI model **`openai/o3-mini-high`** using LangChain’s `ChatOpenAI`.
- Exposes a preconfigured `ChatModel` instance (`model`) ready to be used by the surrounding Naas ABI marketplace framework.

## Public API
- `class O3MiniHighModel(ModelDefinition)`
  - Purpose: Provides metadata and a configured `ChatModel` for the `openai/o3-mini-high` model.
  - Public class attributes:
    - `CANONICAL_ID`: `CanonicalModelId.O3_MINI_HIGH`
    - `MODEL_ID`: `"openai/o3-mini-high"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` (preconfigured)
- `model: ChatModel`
  - Purpose: Module-level alias to `O3MiniHighModel.model` for convenient imports.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - Naas ABI core types: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for configuration
- Configuration required:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build `api_key=SecretStr(...)`).
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.o3_mini_high import model

# `model.model` is a LangChain ChatOpenAI instance configured for OpenRouter.
llm = model.model

# Example invocation shape depends on your LangChain version and message types.
# This file only provides the configured client and metadata.
```

## Caveats
- This module only defines/configures the model; it does not implement invocation helpers.
- Requires a valid OpenRouter API key accessible via `ABIModule` configuration.

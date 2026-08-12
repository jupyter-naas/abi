# Gpt51Model

## What it is
- Defines an OpenRouter-backed LangChain chat model for **OpenAI `openai/gpt-5.1`**.
- Exposes a ready-to-use `ChatModel` instance configured with:
  - `ChatOpenAI` (from `langchain_openai`)
  - OpenRouter base URL: `https://openrouter.ai/api/v1`
  - API key sourced from `ABIModule` configuration

## Public API
- `class Gpt51Model(ModelDefinition)`
  - Purpose: Registers model metadata and a preconfigured `ChatModel`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GPT_5_1`
    - `MODEL_ID`: `"openai/gpt-5.1"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: Fully configured chat model instance (includes metadata like context window, pricing, etc.)
- `model: ChatModel`
  - Module-level alias to `Gpt51Model.model` for convenience.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build `ChatOpenAI(api_key=SecretStr(...))`).
- Hardcoded runtime settings (in `ChatOpenAI` construction):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url="https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_1 import model

# `model.model` is the underlying LangChain ChatOpenAI instance
llm = model.model

# Example call (LangChain-style). Adjust to your LangChain version if needed.
resp = llm.invoke("Say hello briefly.")
print(resp)
```

## Caveats
- The OpenRouter API key must be available via `ABIModule` configuration at import time (the model is instantiated during module import).
- Network calls, timeouts, and retries are controlled by the fixed `timeout=120` and `max_retries=3` configuration.

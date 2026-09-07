# Gemma431BItModel

## What it is
- Defines a **LangChain `ChatOpenAI`** chat model configuration for **OpenRouter** using the model ID `google/gemma-4-31b-it`.
- Exposes a ready-to-use `ChatModel` instance as a module-level `model`.

## Public API
- `class Gemma431BItModel(ModelDefinition)`
  - Purpose: Registers model metadata and builds a `ChatModel` instance for the Gemma 4 31B IT model on OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.GEMMA_4_31B_IT`
    - `MODEL_ID`: `"google/gemma-4-31b-it"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` preconfigured with:
      - `ChatOpenAI(model=MODEL_ID, temperature=0, timeout=120, max_retries=3, base_url="https://openrouter.ai/api/v1")`
      - `api_key` sourced from `ABIModule.get_instance().configuration.openrouter_api_key`
- `model: ChatModel`
  - Purpose: Convenience alias to `Gemma431BItModel.model`.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration required:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to authenticate to OpenRouter).
- Endpoint:
  - Base URL is fixed to `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.google.gemma_4_31b_it import model

# LangChain ChatOpenAI instance is available at:
llm = model.model  # ChatOpenAI

response = llm.invoke("Say hello in one sentence.")
print(response.content)
```

## Caveats
- Temperature is hard-coded to `0` (deterministic behavior).
- Timeout is set to `120` seconds and `max_retries` to `3`.
- Requires a valid OpenRouter API key available via the `ABIModule` configuration.

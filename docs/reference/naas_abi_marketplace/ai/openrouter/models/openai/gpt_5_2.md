# Gpt52Model

## What it is
- Defines the **OpenRouter-hosted OpenAI GPT-5.2** chat model as a `ModelDefinition`.
- Exposes a ready-to-use `ChatModel` configured with `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt52Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5_2`
  - `MODEL_ID`: `"openai/gpt-5.2"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully configured `ChatModel` instance (includes metadata like context window, pricing, supported parameters).
- `model: ChatModel`
  - Module-level alias to `Gpt52Model.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`
- **External configuration**
  - Reads the OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
- **Network endpoint**
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_2 import model

# `model.model` is a langchain_openai.ChatOpenAI instance
llm = model.model

# Example LangChain call pattern (message types depend on your LangChain version)
result = llm.invoke("Hello from GPT-5.2 via OpenRouter")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration; model instantiation uses it immediately.
- The underlying `ChatOpenAI` is configured with:
  - `temperature=0`, `timeout=120`, `max_retries=3`, and `base_url` set to OpenRouter.

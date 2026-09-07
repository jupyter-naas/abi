# Gpt55Model

## What it is
- Defines the **OpenRouter**-hosted **OpenAI GPT-5.5** chat model as a `ModelDefinition`.
- Exposes a ready-to-use `ChatModel` instance configured with `langchain_openai.ChatOpenAI`.

## Public API
- `class Gpt55Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5_5`
  - `MODEL_ID`: `"openai/gpt-5.5"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model wrapper (includes metadata like context window, pricing, supported parameters).
- `model: ChatModel`
  - Module-level alias to `Gpt55Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` (used as the OpenRouter API key).
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_5 import model

# model.model is a langchain_openai.ChatOpenAI instance
llm = model.model

result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- The API key is pulled from `ABIModule` configuration at import time; ensure `ABIModule` is initialized/configured before importing this module.
- The underlying `ChatOpenAI` is configured with `temperature=0`, `timeout=120`, `max_retries=3`, and the OpenRouter base URL.

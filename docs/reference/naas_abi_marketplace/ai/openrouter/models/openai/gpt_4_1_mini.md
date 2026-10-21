# Gpt41MiniModel

## What it is
- A model definition that registers the **OpenRouter**-hosted **OpenAI `gpt-4.1-mini`** chat model as a `ChatModel` using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `model` object configured with OpenRouter base URL and API key pulled from `ABIModule` configuration.

## Public API
- `class Gpt41MiniModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_4_1_MINI`
  - `MODEL_ID`: `"openai/gpt-4.1-mini"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured `ChatModel` instance wrapping `ChatOpenAI`.
- `model: ChatModel`
  - Module-level alias to `Gpt41MiniModel.model`.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for API key resolution
  - `pydantic.SecretStr`
- Configuration values:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
  - API key sourced from: `ABIModule.get_instance().configuration.openrouter_api_key`
- `ChatOpenAI` is constructed with:
  - `model="openai/gpt-4.1-mini"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`
  - `api_key=SecretStr(...)`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_4_1_mini import model

# `model.model` is a langchain_openai.ChatOpenAI instance
llm = model.model

# Example call (method availability depends on your LangChain version)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- Network calls go to OpenRouter (`https://openrouter.ai/api/v1`) and will fail if unreachable or misconfigured.

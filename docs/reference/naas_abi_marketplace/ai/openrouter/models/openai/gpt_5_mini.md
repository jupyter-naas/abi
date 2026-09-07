# `Gpt5MiniModel`

## What it is
- A `ModelDefinition` that registers an OpenRouter-hosted OpenAI chat model (`openai/gpt-5-mini`) using `langchain_openai.ChatOpenAI`.
- Exposes a preconfigured `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class Gpt5MiniModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.GPT_5_MINI`
  - `MODEL_ID`: `"openai/gpt-5-mini"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully configured `ChatModel` wrapping a `ChatOpenAI` client pointed at OpenRouter.
- `model: ChatModel`
  - Module-level alias for `Gpt5MiniModel.model` (convenience import).

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration source**
  - API key is loaded from: `ABIModule.get_instance().configuration.openrouter_api_key`
- **OpenRouter base URL**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **ChatOpenAI settings**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`
  - `api_key=SecretStr(...)`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.openai.gpt_5_mini import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example call style depends on your LangChain version and message types.
# The snippet below only shows how to retrieve the configured client.
print(model.model_id)   # "openai/gpt-5-mini"
print(model.provider)   # ModelProvider.OPENROUTER
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule` configuration (`openrouter_api_key`).
- The module defines metadata such as supported/default parameters, but does not implement validation or invocation helpers beyond the underlying `ChatOpenAI` client.

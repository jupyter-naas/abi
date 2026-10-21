# ClaudeSonnet45Model

## What it is
- A model definition for the OpenRouter-hosted **Anthropic Claude Sonnet 4.5** chat model.
- Provides a ready-to-use `ChatModel` wrapping a `langchain_openai.ChatOpenAI` client configured for OpenRouter.

## Public API
- `class ClaudeSonnet45Model(ModelDefinition)`
  - Declares a `ModelDefinition` with:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_4_5`
    - `MODEL_ID`: `"anthropic/claude-sonnet-4.5"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: preconfigured chat model instance.
- Module-level:
  - `model: ChatModel`: alias to `ClaudeSonnet45Model.model`

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types: `CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- API key source:
  - `ABIModule.get_instance().configuration.openrouter_api_key`
- Client configuration (as constructed in code):
  - `temperature=0`, `timeout=120`, `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_sonnet_4_5 import model

# `model.model` is the underlying LangChain ChatOpenAI instance
llm = model.model

# Example invocation (message format depends on your LangChain version)
result = llm.invoke("Hello from Claude Sonnet 4.5 via OpenRouter!")
print(result)
```

## Caveats
- The API key is pulled from `ABIModule` configuration at import time; missing/invalid configuration will prevent instantiation.
- The `ChatModel` metadata (context window, pricing, supported/default parameters) is static data in this module and does not enforce runtime limits by itself.

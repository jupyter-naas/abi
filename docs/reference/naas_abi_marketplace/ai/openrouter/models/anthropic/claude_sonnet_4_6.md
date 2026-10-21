# ClaudeSonnet46Model

## What it is
- Defines an OpenRouter-backed LangChain chat model configuration for **Anthropic Claude Sonnet 4.6**.
- Exposes a ready-to-use `ChatModel` instance (`model`) configured with `langchain_openai.ChatOpenAI`.

## Public API
- `class ClaudeSonnet46Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_4_6`
  - `MODEL_ID`: `"anthropic/claude-sonnet-4.6"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Fully configured chat model definition (provider, metadata, pricing, architecture, and underlying `ChatOpenAI` instance).
- `model: ChatModel`
  - Module-level alias to `ClaudeSonnet46Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **ChatOpenAI defaults in this file**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="anthropic/claude-sonnet-4.6"`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_sonnet_4_6 import model

# Underlying LangChain chat model (ChatOpenAI)
llm = model.model

# Example call (LangChain API)
result = llm.invoke("Say hello in one short sentence.")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available via `ABIModule.get_instance().configuration.openrouter_api_key`.
- Network calls will use `https://openrouter.ai/api/v1` with a 120s timeout and up to 3 retries as configured here.

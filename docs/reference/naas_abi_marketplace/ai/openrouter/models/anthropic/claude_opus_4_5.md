# ClaudeOpus45Model

## What it is
- A model definition that registers Anthropic **Claude Opus 4.5** via **OpenRouter** as a `ChatModel`.
- Wraps a `langchain_openai.ChatOpenAI` client configured for the OpenRouter API.

## Public API
- `class ClaudeOpus45Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_5`
  - `MODEL_ID`: `"anthropic/claude-opus-4.5"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model instance (includes metadata like context window, pricing, supported parameters).
- `model: ChatModel`
  - Module-level alias to `ClaudeOpus45Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build `SecretStr(...)`).
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **Client defaults**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_5 import model

# 'model' is a ChatModel wrapper; the underlying LangChain client is in model.model
client = model.model

# Example invocation shape depends on your LangChain version and message types.
# This shows the simplest call pattern commonly supported:
response = client.invoke("Hello from Claude Opus 4.5 via OpenRouter.")
print(response)
```

## Caveats
- Importing this module requires OpenRouter API key availability via `ABIModule` configuration; otherwise initialization may fail.
- The runnable invocation interface (`invoke`, message objects) is determined by the installed `langchain_openai`/LangChain versions.

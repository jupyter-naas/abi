# Claude3HaikuModel

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted Anthropic model **`anthropic/claude-3-haiku`** as a `ChatModel` using `langchain_openai.ChatOpenAI`.

## Public API
- `class Claude3HaikuModel(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_3_HAIKU`
  - `MODEL_ID`: `"anthropic/claude-3-haiku"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured `ChatModel` instance (wraps a `ChatOpenAI` client).
- `model: ChatModel`
  - Module-level alias to `Claude3HaikuModel.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads the OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **Client defaults**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_3_haiku import model

# Access the underlying LangChain chat model/client
llm = model.model

# Example call (method name depends on your LangChain version)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Requires `ABIModule` to be initialized/configured so `openrouter_api_key` is available; otherwise model construction may fail at import time.
- This module only defines configuration/metadata; request/response behavior is determined by `langchain_openai.ChatOpenAI` and the OpenRouter backend.

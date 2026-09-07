# ClaudeOpus47Model

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted Anthropic model **`anthropic/claude-opus-4.7`** as a `ChatModel`.
- Provides a ready-to-use `ChatOpenAI` client configured for OpenRouter.

## Public API
- `class ClaudeOpus47Model(ModelDefinition)`
  - Constants:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_7`
    - `MODEL_ID`: `"anthropic/claude-opus-4.7"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - Attribute:
    - `model: ChatModel`: Fully constructed chat model wrapper, including metadata (context window, pricing, supported parameters, etc.) and an underlying `ChatOpenAI` instance.
- `model: ChatModel`
  - Module-level alias to `ClaudeOpus47Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Runtime configuration**
  - Reads API key from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL: `https://openrouter.ai/api/v1`
- **Client settings (hardcoded)**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_7 import model

# Access the underlying LangChain chat model client
llm = model.model  # ChatOpenAI instance

# Example invocation (message format depends on your LangChain version)
result = llm.invoke("Hello from Opus 4.7 via OpenRouter")
print(result)
```

## Caveats
- Requires a valid OpenRouter API key available at `ABIModule.get_instance().configuration.openrouter_api_key`.
- The module instantiates the `ChatOpenAI` client at import time; failures in configuration may raise during import.

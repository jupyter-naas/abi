# ClaudeOpus4Model

## What it is
- A model definition that registers the OpenRouter-hosted **Anthropic Claude Opus 4** chat model as a `ChatModel`.
- Preconfigures a `langchain_openai.ChatOpenAI` client to call OpenRouter (`https://openrouter.ai/api/v1`) with fixed runtime defaults (e.g., `timeout=120`, `max_retries=3`).

## Public API
- `class ClaudeOpus4Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4`
  - `MODEL_ID`: `"anthropic/claude-opus-4"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Holds metadata (name, owner, context window, pricing, etc.) and the underlying `ChatOpenAI` instance.
- `model: ChatModel`
  - Module-level alias to `ClaudeOpus4Model.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- **Configuration**
  - Requires an OpenRouter API key available at:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - OpenRouter base URL is fixed to `https://openrouter.ai/api/v1`.

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4 import model

# Access the underlying LangChain ChatOpenAI client
llm = model.model

# Example invocation (requires ABIModule configuration with openrouter_api_key)
result = llm.invoke("Write a one-line Python function that adds two numbers.")
print(result)
```

## Caveats
- The OpenRouter API key must be correctly configured in `ABIModule` or client initialization will fail.
- The `ChatOpenAI` client is instantiated at import time as part of the `ChatModel` definition.

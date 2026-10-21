# ClaudeOpus46Model

## What it is
- A predefined **OpenRouter** chat model definition for **Anthropic Claude Opus 4.6**, packaged as a `ModelDefinition`.
- Exposes a ready-to-use `ChatModel` backed by `langchain_openai.ChatOpenAI`, configured for OpenRouter.

## Public API
- `class ClaudeOpus46Model(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_6`
    - `MODEL_ID`: `"anthropic/claude-opus-4.6"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - A fully constructed `ChatModel` including metadata (context window, pricing, supported parameters, etc.) and a `ChatOpenAI` instance.

- `model: ChatModel`
  - Module-level alias to `ClaudeOpus46Model.model`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

- **API key source**
  - `ABIModule.get_instance().configuration.openrouter_api_key`

- **ChatOpenAI configuration used**
  - `model="anthropic/claude-opus-4.6"`
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url="https://openrouter.ai/api/v1"`
  - `api_key=SecretStr(<openrouter_api_key>)`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_6 import model

# model.model is the underlying langchain_openai ChatOpenAI instance
llm = model.model

# Example invocation (LangChain message format)
result = llm.invoke([{"role": "user", "content": "Hello from Claude Opus 4.6 via OpenRouter."}])
print(result)
```

## Caveats
- Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set; otherwise model initialization will fail when the module is imported/used.
- `temperature` is configured to `0` in this definition.

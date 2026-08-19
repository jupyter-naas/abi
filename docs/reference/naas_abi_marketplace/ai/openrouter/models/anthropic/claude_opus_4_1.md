# ClaudeOpus41Model

## What it is
- A `ModelDefinition` that registers/configures Anthropic **Claude Opus 4.1** for use via **OpenRouter**, using `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) preconfigured with model metadata and runtime settings.

## Public API
- `class ClaudeOpus41Model(ModelDefinition)`
  - Purpose: Defines the model’s canonical ID, provider, OpenRouter model ID, and a fully configured `ChatModel`.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_1`
    - `MODEL_ID`: `"anthropic/claude-opus-4.1"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model`: `ChatModel` (includes the underlying `ChatOpenAI` client and model metadata)
- `model: ChatModel`
  - Purpose: Module-level alias to `ClaudeOpus41Model.model` for convenient import.

## Configuration/Dependencies
- Depends on:
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule` for API key retrieval
  - `pydantic.SecretStr`
- Uses OpenRouter base URL:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- Requires configuration value:
  - `ABIModule.get_instance().configuration.openrouter_api_key`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_1 import model

# Access the underlying LangChain chat client
llm = model.model

# Minimal call (LangChain-style)
result = llm.invoke("Hello! Summarize what you can do in one sentence.")
print(result.content)
```

## Caveats
- API key must be available via `ABIModule.get_instance().configuration.openrouter_api_key`; otherwise initialization will fail.
- The underlying client is configured with `temperature=0`, `timeout=120`, and `max_retries=3`.

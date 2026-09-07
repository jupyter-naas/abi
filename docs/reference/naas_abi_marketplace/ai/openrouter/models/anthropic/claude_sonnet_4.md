# ClaudeSonnet4Model

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted **Anthropic Claude Sonnet 4** chat model for use via `langchain_openai.ChatOpenAI`.
- Exposes a ready-to-use `ChatModel` instance (`model`) with metadata (context window, pricing, supported parameters, etc.).

## Public API
- `class ClaudeSonnet4Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_4`
  - `MODEL_ID`: `"anthropic/claude-sonnet-4"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`: Preconfigured chat model wrapper around `ChatOpenAI`.
- `model: ChatModel`
  - Module-level alias for `ClaudeSonnet4Model.model`.

## Configuration/Dependencies
- **OpenRouter endpoint**
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- **API key source**
  - Pulled from: `ABIModule.get_instance().configuration.openrouter_api_key`
  - Passed to `ChatOpenAI` as `api_key=SecretStr(...)`
- **Key dependencies**
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.models.Model` (`ModelDefinition`, `ChatModel`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
  - `pydantic.SecretStr`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_sonnet_4 import model

# Access the underlying LangChain chat model
llm = model.model  # ChatOpenAI instance

# Example call (LangChain API)
result = llm.invoke("Write a one-line summary of Claude Sonnet 4.")
print(result)
```

## Caveats
- Requires `ABIModule` configuration to provide a valid `openrouter_api_key`.
- `ChatOpenAI` is instantiated with `temperature=0`, `timeout=120`, and `max_retries=3` in this definition.

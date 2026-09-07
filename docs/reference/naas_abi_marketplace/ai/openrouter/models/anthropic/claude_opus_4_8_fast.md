# ClaudeOpus48FastModel

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted Anthropic model **`anthropic/claude-opus-4.8-fast`** as a `ChatModel` backed by `langchain_openai.ChatOpenAI`.
- Exposes a module-level `model` object for convenient imports.

## Public API
- `class ClaudeOpus48FastModel(ModelDefinition)`
  - Static identifiers:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_8_FAST`
    - `MODEL_ID`: `"anthropic/claude-opus-4.8-fast"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Preconfigured `ChatModel` instance using `ChatOpenAI` with:
      - `temperature=0`
      - `timeout=120`
      - `max_retries=3`
      - `base_url="https://openrouter.ai/api/v1"`
      - `api_key` read from `ABIModule.get_instance().configuration.openrouter_api_key`
- `model: ChatModel`
  - Alias to `ClaudeOpus48FastModel.model` for direct import/use.

## Configuration/Dependencies
- Dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` types (`ModelDefinition`, `ChatModel`, etc.)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Required configuration:
  - `ABIModule.get_instance().configuration.openrouter_api_key` must be set (used to build the `SecretStr` API key).

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_8_fast import model

# Access the underlying LangChain chat model
llm = model.model

# Example invocation (LangChain style)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- This module configures the client to use OpenRouter (`base_url="https://openrouter.ai/api/v1"`); it will fail if the OpenRouter API key is not available via `ABIModule` configuration.

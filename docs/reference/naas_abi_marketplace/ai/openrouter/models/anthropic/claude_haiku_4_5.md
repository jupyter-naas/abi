# ClaudeHaiku45Model

## What it is
- A model definition for **Anthropic Claude Haiku 4.5** hosted via **OpenRouter**, wired as a `ChatOpenAI` (LangChain) chat model.
- Exposes a ready-to-use `ChatModel` instance (`model`) with fixed defaults (temperature, timeout, retries, base URL).

## Public API
- `class ClaudeHaiku45Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_HAIKU_4_5`
  - `MODEL_ID`: `"anthropic/claude-haiku-4.5"`
  - `PROVIDER`: `ModelProvider.OPENROUTER`
  - `model: ChatModel`
    - Contains:
      - `model_id`, `provider`, and a `ChatOpenAI` instance configured for OpenRouter
      - Metadata such as `context_window`, `name`, `owner`, `description`, `created_at`, `pricing`, `architecture`, and `supported_parameters`

- `model: ChatModel`
  - Module-level alias to `ClaudeHaiku45Model.model` for convenience.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`

- **Runtime configuration**
  - Reads OpenRouter API key from:
    - `ABIModule.get_instance().configuration.openrouter_api_key`
  - Uses OpenRouter base URL:
    - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`

- **ChatOpenAI defaults**
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `model="anthropic/claude-haiku-4.5"`
  - `base_url="https://openrouter.ai/api/v1"`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_haiku_4_5 import model

# LangChain ChatOpenAI instance:
llm = model.model

# Minimal invocation (LangChain supports multiple message formats; keep it simple here)
result = llm.invoke("Say hello in one sentence.")
print(result)
```

## Caveats
- Importing this module requires a working `ABIModule` configuration; `openrouter_api_key` must be available at import time because the `ChatOpenAI` instance is constructed immediately.

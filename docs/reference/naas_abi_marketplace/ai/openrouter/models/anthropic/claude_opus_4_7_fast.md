# ClaudeOpus47FastModel

## What it is
- A `ModelDefinition` that registers/configures the OpenRouter-hosted Anthropic model **`anthropic/claude-opus-4.7-fast`** as a LangChain `ChatOpenAI` chat model.
- Exposes a ready-to-use `ChatModel` instance via the module-level `model`.

## Public API
- `class ClaudeOpus47FastModel(ModelDefinition)`
  - Purpose: defines metadata and a fully configured `ChatModel` for Claude Opus 4.7 Fast on OpenRouter.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_7_FAST`
    - `MODEL_ID`: `"anthropic/claude-opus-4.7-fast"`
    - `PROVIDER`: `ModelProvider.OPENROUTER`
    - `model: ChatModel`: configured model wrapper (includes the underlying LangChain `ChatOpenAI` client and metadata such as context window, pricing, etc.)
- `model: ChatModel`
  - Purpose: module-level alias to `ClaudeOpus47FastModel.model` for convenience.

## Configuration/Dependencies
- External dependencies:
  - `langchain_openai.ChatOpenAI`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.openrouter.ABIModule`
- Configuration:
  - Requires `ABIModule.get_instance().configuration.openrouter_api_key` to be set.
- OpenRouter endpoint:
  - `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- Client defaults (as configured here):
  - `temperature=0`
  - `timeout=120`
  - `max_retries=3`
  - `base_url=OPENROUTER_BASE_URL`

## Usage
```python
from naas_abi_marketplace.ai.openrouter.models.anthropic.claude_opus_4_7_fast import model

# Access the underlying LangChain ChatOpenAI instance:
llm = model.model

# Example invocation (LangChain style):
response = llm.invoke("Say hello in one sentence.")
print(response)
```

## Caveats
- Importing this module will attempt to read the OpenRouter API key from `ABIModule` configuration; missing/invalid configuration will prevent correct client setup.
- The model is configured with a fixed `base_url` for OpenRouter and `temperature=0` in code.

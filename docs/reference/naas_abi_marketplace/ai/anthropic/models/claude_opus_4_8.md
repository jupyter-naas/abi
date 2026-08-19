# ClaudeOpus48Model

## What it is
- A `ModelDefinition` that registers/configures the Anthropic **Claude Opus 4.8** chat model for the Naas ABI marketplace.
- Exposes a ready-to-use `ChatModel` instance (`model`) backed by `langchain_anthropic.ChatAnthropic`.

## Public API
- `class ClaudeOpus48Model(ModelDefinition)`
  - Purpose: defines metadata and a configured `ChatModel` for Claude Opus 4.8.
  - Public attributes:
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_OPUS_4_8`
    - `MODEL_ID`: `"claude-opus-4-8"`
    - `PROVIDER`: `ModelProvider.ANTHROPIC`
    - `model: ChatModel`: fully configured chat model wrapper (includes LangChain `ChatAnthropic` instance and model metadata).
- `model: ChatModel`
  - Purpose: module-level alias to `ClaudeOpus48Model.model` for convenient imports.

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `ModelProvider`, `CanonicalModelId`)
  - `naas_abi_marketplace.ai.anthropic.ABIModule` (for configuration)
- Runtime configuration:
  - Reads the Anthropic API key from:
    - `ABIModule.get_instance().configuration.anthropic_api_key`
- Key model settings (as configured in code):
  - `max_retries=2`
  - `max_tokens_to_sample=8192` (explicitly set)
  - `timeout=None`
  - `stop=None`
  - `context_window=1000000` (metadata on `ChatModel`)

## Usage
```python
from naas_abi_marketplace.ai.anthropic.models.claude_opus_4_8 import model

# The underlying LangChain chat model is available at model.model
llm = model.model

# Use standard LangChain invocation patterns (depending on your langchain version)
result = llm.invoke("Write a one-sentence summary of what this model is.")
print(result)
```

## Caveats
- Requires a valid Anthropic API key available via `ABIModule` configuration; otherwise initialization will fail when accessing `configuration.anthropic_api_key`.
- The LangChain wrapper is configured with `max_tokens_to_sample=8192`; higher output limits advertised in metadata (e.g., `max_completion_tokens`, `max_output_tokens`) are not enforced by this code.

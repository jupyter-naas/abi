# `claude_opus_4_1`

## What it is
- A module-level definition of a `ChatModel` configured to use Anthropic’s `claude-opus-4-1-20250805` via `langchain_anthropic.ChatAnthropic`.
- Intended to be imported and used as a ready-to-run chat model instance.

## Public API
- **Constants**
  - `MODEL_ID: str` — Anthropic model name (`"claude-opus-4-1-20250805"`).
  - `PROVIDER: str` — Provider identifier (`"anthropic"`).
- **Objects**
  - `model: ChatModel` — Preconfigured chat model wrapper.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_marketplace.ai.claude.ABIModule` (for configuration access)
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.anthropic_api_key` must be set (used as the Anthropic API key).
- **ChatAnthropic parameters set**
  - `model_name=MODEL_ID`
  - `temperature=0`
  - `max_retries=2`
  - `timeout=None`
  - `stop=None`

## Usage
```python
from naas_abi_marketplace.ai.claude.models.claude_opus_4_1 import model

# Use `model` wherever a `ChatModel` instance is expected in your codebase.
print(model.model_id)   # "claude-opus-4-1-20250805"
print(model.provider)   # "anthropic"
```

## Caveats
- This module only defines configuration and instantiates the model; it does not define helper functions for prompting or execution.
- If `anthropic_api_key` is missing/invalid in `ABIModule` configuration, initialization or downstream calls will fail.

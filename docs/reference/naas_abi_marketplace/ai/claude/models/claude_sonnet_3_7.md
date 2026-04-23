# claude_sonnet_3_7

## What it is
- A module-level configuration that instantiates a `ChatModel` wrapper for Anthropic’s `claude-3-7-sonnet-20250219` via `langchain_anthropic.ChatAnthropic`.

## Public API
- **Constants**
  - `MODEL_ID: str` — `"claude-3-7-sonnet-20250219"`
  - `PROVIDER: str` — `"anthropic"`
- **Variables**
  - `model: ChatModel` — Preconfigured chat model instance.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_marketplace.ai.claude.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Configuration source**
  - Reads API key from: `ABIModule.get_instance().configuration.anthropic_api_key`
- **Model configuration**
  - `model_name = MODEL_ID`
  - `temperature = 0`
  - `max_retries = 2`
  - `timeout = None`
  - `stop = None`

## Usage
```python
from naas_abi_marketplace.ai.claude.models.claude_sonnet_3_7 import model

# model is a preconfigured ChatModel instance
print(model.model_id, model.provider)
```

## Caveats
- Importing this module requires `ABIModule` to be initialized/configured such that `configuration.anthropic_api_key` is available.

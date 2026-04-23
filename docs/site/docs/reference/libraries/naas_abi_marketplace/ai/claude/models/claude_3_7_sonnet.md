# claude_3_7_sonnet

## What it is
- Defines a preconfigured Anthropic Claude chat model (`claude-3-7-sonnet-20250219`) wrapped as a `naas_abi_core.models.Model.ChatModel`.
- Intended to be imported and used as a ready-to-run model instance.

## Public API
- `MODEL_ID: str`
  - Constant model identifier: `"claude-3-7-sonnet-20250219"`.
- `PROVIDER: str`
  - Constant provider identifier: `"anthropic"`.
- `model: ChatModel`
  - A `ChatModel` instance configured with:
    - underlying `langchain_anthropic.ChatAnthropic`
    - `temperature=0`
    - `max_retries=2`
    - `timeout=None`
    - `stop=None`
    - `api_key` sourced from `ABIModule.get_instance().configuration.anthropic_api_key` (wrapped in `pydantic.SecretStr`)

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_marketplace.ai.claude.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- Requires configuration:
  - `ABIModule.get_instance().configuration.anthropic_api_key` must be set to a valid Anthropic API key.

## Usage
```python
from naas_abi_marketplace.ai.claude.models.claude_3_7_sonnet import model

# Use `model` with the interfaces expected by your application.
# (The exact invocation methods depend on ChatModel's implementation.)
print(model.model_id, model.provider)
```

## Caveats
- Importing this module constructs the model immediately and reads the API key from `ABIModule` configuration at import time.
- The callable methods for sending chat messages are not defined here; they depend on `ChatModel` and the underlying `ChatAnthropic` object.

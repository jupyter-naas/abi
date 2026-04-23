# claude_sonnet_4_5

## What it is
- A module-level definition of a `ChatModel` configured to use Anthropic’s `ChatAnthropic` backend for the `claude-sonnet-4-5-20250929` model.

## Public API
- **Constants**
  - `MODEL_ID: str` — `"claude-sonnet-4-5-20250929"`.
  - `PROVIDER: str` — `"anthropic"`.
- **Objects**
  - `model: ChatModel` — Preconfigured chat model wrapper containing a `ChatAnthropic` instance.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.claude.ABIModule`
  - `pydantic.SecretStr`
- **Configuration source**
  - `ABIModule.get_instance().configuration.anthropic_api_key` is used as the API key (wrapped in `SecretStr`).
- **Model settings**
  - `temperature=0`
  - `max_retries=2`
  - `timeout=None`
  - `stop=None`

## Usage
```python
from naas_abi_marketplace.ai.claude.models.claude_sonnet_4_5 import model

# Use `model` wherever a ChatModel is expected in your application.
# Example (introspection):
print(model.model_id, model.provider)
```

## Caveats
- Requires a valid `anthropic_api_key` available via `ABIModule` configuration; otherwise instantiation/import may fail.

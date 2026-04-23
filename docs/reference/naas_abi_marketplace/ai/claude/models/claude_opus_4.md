# claude_opus_4

## What it is
- A module-level `ChatModel` instance configured to use Anthropic’s `claude-opus-4-20250514` via `langchain_anthropic.ChatAnthropic`.
- Intended as a ready-to-import model definition for the Naas ABI marketplace Claude integration.

## Public API
- `MODEL_ID: str`
  - Constant model identifier: `"claude-opus-4-20250514"`.
- `PROVIDER: str`
  - Constant provider name: `"anthropic"`.
- `model: naas_abi_core.models.Model.ChatModel`
  - Preconfigured chat model wrapper containing a `ChatAnthropic` client.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_marketplace.ai.claude.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.anthropic_api_key` must be set; it is wrapped in `SecretStr` and passed as `api_key`.

## Usage
```python
from naas_abi_marketplace.ai.claude.models.claude_opus_4 import model

# model is a ChatModel wrapping a ChatAnthropic instance
print(model.model_id)   # "claude-opus-4-20250514"
print(model.provider)   # "anthropic"
```

## Caveats
- The module constructs the underlying `ChatAnthropic` client at import time; missing/invalid `anthropic_api_key` in `ABIModule` configuration can cause import-time errors.
- Client settings are fixed in this module:
  - `temperature=0`, `max_retries=2`, `timeout=None`, `stop=None`.

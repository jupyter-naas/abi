# claude_sonnet_4

## What it is
- A module-level definition of a **preconfigured Anthropic Claude Sonnet 4 chat model** wrapped in `naas_abi_core.models.Model.ChatModel`.
- Exposes constants for the model ID and provider plus a ready-to-use `model` object.

## Public API
- `MODEL_ID: str`
  - The Anthropic model name: `"claude-sonnet-4-20250514"`.
- `PROVIDER: str`
  - Provider identifier: `"anthropic"`.
- `model: ChatModel`
  - A `ChatModel` instance configured with:
    - `model_id=MODEL_ID`
    - `provider=PROVIDER`
    - `model=ChatAnthropic(...)` using:
      - `model_name=MODEL_ID`
      - `temperature=0`
      - `max_retries=2`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key)`
      - `timeout=None`
      - `stop=None`

## Configuration/Dependencies
- Dependencies:
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_marketplace.ai.claude.ABIModule` (used to fetch configuration)
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- Required configuration:
  - `ABIModule.get_instance().configuration.anthropic_api_key` must be set and accessible at import time.

## Usage
```python
from naas_abi_marketplace.ai.claude.models.claude_sonnet_4 import model

# Use `model` with the APIs expected by `naas_abi_core.models.Model.ChatModel`.
# (Exact invocation depends on ChatModel's interface in your environment.)
print(model.model_id, model.provider)
```

## Caveats
- Import-time initialization:
  - The module constructs the model on import; missing/invalid `anthropic_api_key` in `ABIModule` configuration can cause import failures.
- Retries/temperature are fixed here (`max_retries=2`, `temperature=0`) unless you modify the source or wrap/replace the model instance.

# ClaudeSonnet45Model

## What it is
- Defines an Anthropic chat model configuration for **Claude Sonnet 4.5** using `langchain_anthropic.ChatAnthropic`.
- Exposes a ready-to-use `ChatModel` instance as a module-level `model`.

## Public API
- `class ClaudeSonnet45Model(ModelDefinition)`
  - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_4_5`
  - `MODEL_ID`: `"claude-sonnet-4-5-20250929"`
  - `PROVIDER`: `ModelProvider.ANTHROPIC`
  - `model: ChatModel`
    - A `ChatModel` wrapping a `ChatAnthropic` client configured with:
      - `model_name=MODEL_ID`
      - `temperature=0`
      - `max_retries=2`
      - `api_key=SecretStr(ABIModule.get_instance().configuration.anthropic_api_key)`
      - `timeout=None`, `stop=None`
- `model: ChatModel`
  - Alias to `ClaudeSonnet45Model.model` for convenient imports.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `pydantic.SecretStr`
  - `naas_abi_core.models.Model` (`ChatModel`, `ModelDefinition`, `CanonicalModelId`, `ModelProvider`)
  - `naas_abi_marketplace.ai.anthropic.ABIModule`
- **Required configuration**
  - `ABIModule.get_instance().configuration.anthropic_api_key` must be set (used as the Anthropic API key).

## Usage
```python
from naas_abi_marketplace.ai.anthropic.models.claude_sonnet_4_5 import model

# `model.model` is the underlying ChatAnthropic client.
client = model.model

# Example call pattern depends on your langchain version.
# Typically you would invoke the client with messages, e.g.:
# response = client.invoke("Hello!")
```

## Caveats
- API key is pulled from `ABIModule` at import time; missing/invalid configuration will break model initialization.
- `timeout=None` means requests may wait indefinitely unless handled elsewhere.

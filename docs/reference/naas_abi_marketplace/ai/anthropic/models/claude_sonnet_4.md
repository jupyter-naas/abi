# ClaudeSonnet4Model

## What it is
- A `ModelDefinition` that registers an Anthropic Claude Sonnet 4 chat model (`claude-sonnet-4-20250514`) for use via `naas_abi_core` as a `ChatModel`.
- Exposes a ready-to-use module-level `model` alias.

## Public API
- **Class `ClaudeSonnet4Model(ModelDefinition)`**
  - **Constants**
    - `CANONICAL_ID`: `CanonicalModelId.CLAUDE_SONNET_4`
    - `MODEL_ID`: `"claude-sonnet-4-20250514"`
    - `PROVIDER`: `ModelProvider.ANTHROPIC`
  - **Attribute**
    - `model: ChatModel`  
      Wraps a `langchain_anthropic.ChatAnthropic` instance configured for this model.
- **Module variable `model: ChatModel`**
  - Alias to `ClaudeSonnet4Model.model` for convenient importing.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_anthropic.ChatAnthropic`
  - `naas_abi_core.models.Model` (`CanonicalModelId`, `ChatModel`, `ModelDefinition`, `ModelProvider`)
  - `naas_abi_marketplace.ai.anthropic.ABIModule`
  - `pydantic.SecretStr`
- **Configuration required**
  - `ABIModule.get_instance().configuration.anthropic_api_key` must be set; it is passed as `api_key=SecretStr(...)`.
- **Model parameters (as constructed)**
  - `temperature=0`
  - `max_retries=2`
  - `timeout=None`
  - `stop=None`

## Usage
```python
from naas_abi_marketplace.ai.anthropic.models.claude_sonnet_4 import model

# `model` is a ChatModel wrapper around a ChatAnthropic instance.
print(model.model_id)     # "claude-sonnet-4-20250514"
print(model.provider)     # ModelProvider.ANTHROPIC
```

## Caveats
- Requires a valid Anthropic API key available via `ABIModule` configuration at import/construction time.

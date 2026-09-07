# mistral_small_2506

## What it is
A module that exports a preconfigured `ChatModel` for Mistral’s `mistral-small-2506`, backed by `langchain_mistralai.ChatMistralAI`.

## Public API
- **Constants**
  - `MODEL_ID`: `"mistral-small-2506"` — Mistral model identifier.
  - `PROVIDER`: `"mistral"` — provider identifier.
  - `TEMPERATURE`: `0` — sampling temperature.
- **Objects**
  - `model: ChatModel` — a `naas_abi_core.models.Model.ChatModel` instance wrapping `ChatMistralAI`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_mistralai.ChatMistralAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.mistral.ABIModule`
  - `pydantic.SecretStr`
- **Configuration**
  - Reads API key from: `ABIModule.get_instance().configuration.mistral_api_key`
  - Passed to `ChatMistralAI` as `api_key=SecretStr(...)`

## Usage
```python
from naas_abi_marketplace.ai.mistral.models.mistral_small_2506 import model

print(model.model_id)   # "mistral-small-2506"
print(model.provider)   # "mistral"
```

## Caveats
- Importing this module instantiates the model immediately and reads `mistral_api_key` from `ABIModule` configuration; missing/invalid configuration can raise errors at import time.
- This module only provides the configured `model`; how to invoke/chat depends on `ChatModel`/`ChatMistralAI` APIs.

# `mistral_large_2411`

## What it is
- A module that exports a preconfigured `ChatModel` wrapping `langchain_mistralai.ChatMistralAI` for Mistral’s `mistral-large-2411` model.

## Public API
- **Constants**
  - `MODEL_ID`: `"mistral-large-2411"` — Mistral model name.
  - `PROVIDER`: `"mistral"` — provider identifier.
  - `TEMPERATURE`: `0` — generation temperature.
- **Objects**
  - `model: ChatModel` — a ready-to-use `ChatModel` configured with `ChatMistralAI(model_name=MODEL_ID, temperature=TEMPERATURE, api_key=...)`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_mistralai.ChatMistralAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.mistral.ABIModule`
  - `pydantic.SecretStr`
- **Configuration source**
  - Reads `ABIModule.get_instance().configuration.mistral_api_key` and passes it as `api_key=SecretStr(...)` to `ChatMistralAI`.

## Usage
```python
from naas_abi_marketplace.ai.mistral.models.mistral_large_2411 import model

print(model.model_id)   # "mistral-large-2411"
print(model.provider)   # "mistral"
```

## Caveats
- Importing this module instantiates `ChatMistralAI` immediately; a valid `ABIModule.get_instance().configuration.mistral_api_key` must be available at import time.

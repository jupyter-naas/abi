# mistral_medium_2508

## What it is
A module that defines a preconfigured `ChatModel` wrapper for Mistral’s `mistral-medium-2508` via `langchain_mistralai.ChatMistralAI`.

## Public API
- **Constants**
  - `MODEL_ID`: `"mistral-medium-2508"` — Mistral model name.
  - `PROVIDER`: `"mistral"` — provider identifier.
  - `TEMPERATURE`: `0` — generation temperature.

- **Objects**
  - `model: ChatModel` — a `naas_abi_core.models.Model.ChatModel` instance wrapping `ChatMistralAI` configured with the above constants and an API key from `ABIModule`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_mistralai.ChatMistralAI`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.mistral.ABIModule`
  - `pydantic.SecretStr`

- **Required configuration**
  - `ABIModule.get_instance().configuration.mistral_api_key` must be set; it is wrapped in `SecretStr` and passed to `ChatMistralAI` as `api_key`.

## Usage
```python
from naas_abi_marketplace.ai.mistral.models.mistral_medium_2508 import model

print(model.model_id)   # "mistral-medium-2508"
print(model.provider)   # "mistral"
```

## Caveats
- Importing this module constructs `ChatMistralAI` immediately; missing/invalid `mistral_api_key` may cause import-time failures.

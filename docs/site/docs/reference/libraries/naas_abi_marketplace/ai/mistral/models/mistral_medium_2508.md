# mistral_medium_2508

## What it is
A module-level definition of a `ChatModel` configured to use Mistral’s **`mistral-medium-2508`** chat model via `langchain_mistralai.ChatMistralAI`.

## Public API
- **Constants**
  - `MODEL_ID`: `"mistral-medium-2508"` — the Mistral model name.
  - `PROVIDER`: `"mistral"` — provider identifier.
  - `TEMPERATURE`: `0` — generation temperature.

- **Objects**
  - `model: ChatModel` — a preconfigured `naas_abi_core.models.Model.ChatModel` wrapping a `ChatMistralAI` instance.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_mistralai.ChatMistralAI`
  - `naas_abi_marketplace.ai.mistral.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`

- **Required configuration**
  - `ABIModule.get_instance().configuration.mistral_api_key` must be set; it is passed as a `SecretStr` to `ChatMistralAI`.

## Usage
```python
from naas_abi_marketplace.ai.mistral.models.mistral_medium_2508 import model

# Use `model` wherever a ChatModel is expected in your application.
print(model.model_id)   # mistral-medium-2508
print(model.provider)   # mistral
```

## Caveats
- Importing the module constructs the underlying `ChatMistralAI` immediately; missing/invalid `mistral_api_key` configuration may cause failures at import time.

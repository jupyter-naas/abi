# `mistral_large_2411`

## What it is
- A module-level definition of a `ChatModel` configured to use Mistral’s `mistral-large-2411` chat model via `langchain_mistralai.ChatMistralAI`.

## Public API
- **Constants**
  - `MODEL_ID`: `"mistral-large-2411"` — Mistral model name.
  - `PROVIDER`: `"mistral"` — provider identifier.
  - `TEMPERATURE`: `0` — fixed generation temperature.
- **Objects**
  - `model: ChatModel` — preconfigured chat model wrapper using `ChatMistralAI`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_mistralai.ChatMistralAI`
  - `naas_abi_marketplace.ai.mistral.ABIModule` (used to read configuration)
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Configuration**
  - Expects `ABIModule.get_instance().configuration.mistral_api_key` to be set; used as the `api_key` for `ChatMistralAI`.

## Usage
```python
from naas_abi_marketplace.ai.mistral.models.mistral_large_2411 import model

# `model` is a ChatModel wrapper around ChatMistralAI configured for mistral-large-2411.
# Use it according to the ChatModel interface available in your environment.
print(model.model_id, model.provider)
```

## Caveats
- Importing this module will instantiate `ChatMistralAI` immediately and will require a valid `mistral_api_key` in `ABIModule` configuration.

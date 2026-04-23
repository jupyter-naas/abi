# mistral_small_2506

## What it is
A module-level definition of a `ChatModel` configured to use Mistral’s `mistral-small-2506` chat model via `langchain_mistralai.ChatMistralAI`.

## Public API
- **Constants**
  - `MODEL_ID`: `"mistral-small-2506"` — Mistral model name/id.
  - `PROVIDER`: `"mistral"` — provider identifier.
  - `TEMPERATURE`: `0` — sampling temperature.
- **Objects**
  - `model: ChatModel` — a preconfigured `naas_abi_core.models.Model.ChatModel` wrapping a `ChatMistralAI` instance.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_mistralai.ChatMistralAI`
  - `naas_abi_marketplace.ai.mistral.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.mistral_api_key` must be set; it is wrapped in `SecretStr` and passed as `api_key` to `ChatMistralAI`.

## Usage
```python
from naas_abi_marketplace.ai.mistral.models.mistral_small_2506 import model

# Use `model` where a ChatModel is expected in your application.
# (Methods are defined by naas_abi_core.models.Model.ChatModel.)
print(model.model_id, model.provider)
```

## Caveats
- This module only instantiates and exports the configured `model`; interaction methods depend on `ChatModel` and `ChatMistralAI` implementations.
- Importing this module will attempt to read `mistral_api_key` from `ABIModule` configuration; missing/invalid configuration may raise errors at import time.

# `sonar_pro_search`

## What it is
- A module-level definition of a `ChatModel` configured to use Perplexity’s `sonar-pro-search` via `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID`: `"sonar-pro-search"` — the Perplexity model name.
  - `PROVIDER`: `"perplexity"` — provider identifier.
- **Objects**
  - `model: ChatModel` — preconfigured chat model wrapper using `ChatPerplexity` with:
    - `temperature=0`
    - `timeout=120`
    - `api_key` sourced from `ABIModule.get_instance().configuration.perplexity_api_key` (wrapped as `pydantic.SecretStr`)

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set to a valid Perplexity API key.

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_pro_search import model

# Use `model` wherever a `ChatModel` is accepted in your application.
# (Invocation methods depend on `ChatModel`'s interface in naas_abi_core.)
print(model.model_id, model.provider)
```

## Caveats
- This file only defines configuration (no functions/classes). Actual calling semantics depend on `ChatModel` and `ChatPerplexity` implementations.

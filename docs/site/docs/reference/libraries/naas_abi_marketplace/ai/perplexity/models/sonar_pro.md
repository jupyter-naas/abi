# sonar_pro

## What it is
Defines a ready-to-use `ChatModel` instance for the Perplexity **sonar-pro** model, backed by `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID: str` — set to `"sonar-pro"`.
  - `PROVIDER: str` — set to `"perplexity"`.
- **Module variable**
  - `model: ChatModel` — a configured `ChatModel` wrapping `ChatPerplexity` with:
    - `model="sonar-pro"`
    - `temperature=0`
    - `timeout=120`
    - `api_key` read from `ABIModule.get_instance().configuration.perplexity_api_key` (wrapped in `pydantic.SecretStr`)

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set (used to authenticate with Perplexity).

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_pro import model

# Use `model` with the APIs expected by `naas_abi_core.models.Model.ChatModel`
# (exact invocation depends on ChatModel's interface).
print(model.model_id, model.provider)
```

## Caveats
- This module only defines and exports a preconfigured `ChatModel`; it does not provide helper functions for sending messages. The calling code must use the `ChatModel` interface provided by `naas_abi_core`.

# sonar_pro

## What it is
Defines a preconfigured `ChatModel` for Perplexity’s **sonar-pro** model using `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID: str` — `"sonar-pro"`
  - `PROVIDER: str` — `"perplexity"`
- **Module variable**
  - `model: ChatModel` — a `ChatModel` wrapping `ChatPerplexity` configured with:
    - `model="sonar-pro"`
    - `temperature=0`
    - `timeout=120`
    - `api_key=SecretStr(ABIModule.get_instance().configuration.perplexity_api_key)`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set to authenticate requests.

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_pro import model

# Access metadata
print(model.model_id)   # "sonar-pro"
print(model.provider)   # "perplexity"

# Use `model` according to the `ChatModel` interface in `naas_abi_core`.
```

## Caveats
- This module only exports a configured `ChatModel`; it does not define message-sending helpers. Use the `ChatModel` interface provided by `naas_abi_core`.

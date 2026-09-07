# `sonar_reasoning_pro`

## What it is
A small module that exports a preconfigured `ChatModel` wrapper for the Perplexity provider using LangChain’s `ChatPerplexity`, pinned to the `sonar-reasoning-pro` model.

## Public API
- **Constants**
  - `MODEL_ID: str` — `"sonar-reasoning-pro"`.
  - `PROVIDER: str` — `"perplexity"`.

- **Objects**
  - `model: ChatModel` — Ready-to-use chat model instance with:
    - underlying client: `langchain_perplexity.ChatPerplexity`
    - settings: `model=MODEL_ID`, `temperature=0`, `timeout=120`
    - `api_key`: loaded from `ABIModule.get_instance().configuration.perplexity_api_key` and wrapped in `pydantic.SecretStr`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `pydantic.SecretStr`

- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set to a valid Perplexity API key.

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_reasoning_pro import model

# Basic introspection
print(model.model_id)
print(model.provider)
```

## Caveats
- Importing the module instantiates `ChatPerplexity` immediately and reads the API key from `ABIModule` configuration.
- `temperature` is fixed to `0` and `timeout` to `120` seconds in this module.

# `sonar_pro_search`

## What it is
- A small module that exposes a preconfigured `ChatModel` for Perplexity’s `sonar-pro-search` via `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID`: `"sonar-pro-search"` — Perplexity model identifier.
  - `PROVIDER`: `"perplexity"` — provider name.
- **Objects**
  - `model: ChatModel` — a `ChatModel` wrapper configured with:
    - `model_id=MODEL_ID`
    - `provider=PROVIDER`
    - `model=ChatPerplexity(model=MODEL_ID, temperature=0, timeout=120, api_key=SecretStr(...))`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `pydantic.SecretStr`
- **Configuration required**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set (used to build `SecretStr(...)` for `ChatPerplexity.api_key`).

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_pro_search import model

# The invocation interface depends on ChatModel (naas_abi_core).
print(model.model_id)   # sonar-pro-search
print(model.provider)   # perplexity
```

## Caveats
- This module only defines configuration and exports `model`; it does not provide call helpers. How to send prompts depends on the `ChatModel` / `ChatPerplexity` interfaces.

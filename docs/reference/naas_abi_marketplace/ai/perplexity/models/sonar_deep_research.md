# sonar_deep_research

## What it is
- A preconfigured Perplexity chat model definition for the `sonar-deep-research` model.
- Exposes a module-level `ChatModel` instance that wraps `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID`: `"sonar-deep-research"` — Perplexity model name.
  - `PROVIDER`: `"perplexity"` — provider identifier.
- **Objects**
  - `model: ChatModel` — ready-to-use `naas_abi_core.models.Model.ChatModel` configured with:
    - underlying model: `ChatPerplexity(model=MODEL_ID, temperature=0, timeout=120, api_key=SecretStr(...))`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be available; it is wrapped in `SecretStr` and passed to `ChatPerplexity`.

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_deep_research import model

# `model` is a ChatModel wrapper; the underlying LangChain model is at `model.model`
chat = model.model
```

## Caveats
- Importing this module reads `ABIModule.get_instance().configuration.perplexity_api_key`; missing/invalid configuration can fail at import time.

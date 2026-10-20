# sonar_deep_research

## What it is
- A preconfigured Perplexity chat model definition for the **`sonar-deep-research`** model.
- Exposes a module-level `ChatModel` instance wired to `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID`: `"sonar-deep-research"` — the Perplexity model name.
  - `PROVIDER`: `"perplexity"` — provider identifier.
- **Objects**
  - `model: ChatModel` — a ready-to-use `naas_abi_core.models.Model.ChatModel` wrapping `ChatPerplexity` with:
    - `temperature=0`
    - `timeout=120`
    - `api_key` sourced from `ABIModule.get_instance().configuration.perplexity_api_key`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Configuration required**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set and accessible.

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models import sonar_deep_research

chat_model = sonar_deep_research.model
# `chat_model.model` is the underlying ChatPerplexity instance.
```

## Caveats
- Importing this module will access `ABIModule.get_instance().configuration.perplexity_api_key`; missing/invalid configuration may raise errors during import.
- The API key is wrapped as `SecretStr`, but you are still responsible for secure configuration management.

# sonar_reasoning

## What it is
A module that exposes a preconfigured `ChatModel` instance targeting Perplexity’s `sonar-reasoning` model via `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID: str = "sonar-reasoning"`: Perplexity model identifier.
  - `PROVIDER: str = "perplexity"`: Provider name used in the wrapper.
- **Variables**
  - `model: ChatModel`: Ready-to-use `naas_abi_core.models.Model.ChatModel` wrapping a `ChatPerplexity` client.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `pydantic.SecretStr`
- **Configuration source**
  - Uses `ABIModule.get_instance().configuration.perplexity_api_key` and wraps it with `SecretStr` for `api_key`.
- **Model parameters**
  - `temperature=0`
  - `timeout=120`
  - `model="sonar-reasoning"`

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_reasoning import model

print(model.model_id)   # sonar-reasoning
print(model.provider)   # perplexity
```

## Caveats
- This module only provides a configured `ChatModel` instance; it does not define invocation helpers.
- Requires `perplexity_api_key` to be available in `ABIModule` configuration.

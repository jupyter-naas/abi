# sonar_reasoning

## What it is
A module-level definition of a `ChatModel` configured to use Perplexity’s `sonar-reasoning` model via `langchain_perplexity.ChatPerplexity`.

## Public API
- **Constants**
  - `MODEL_ID: str = "sonar-reasoning"`: The Perplexity model name.
  - `PROVIDER: str = "perplexity"`: Provider identifier.
- **Variables**
  - `model: ChatModel`: Preconfigured chat model wrapper (`naas_abi_core.models.Model.ChatModel`) using `ChatPerplexity`.

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_marketplace.ai.perplexity.ABIModule` (for configuration access)
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Configuration**
  - Reads `ABIModule.get_instance().configuration.perplexity_api_key` to set `api_key` (wrapped in `SecretStr`).
- **Model settings**
  - `temperature=0`
  - `timeout=120`

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_reasoning import model

# Use `model` according to the ChatModel interface provided by naas_abi_core.
# (Method names depend on ChatModel; this module only exposes the configured instance.)
print(model.model_id)   # "sonar-reasoning"
print(model.provider)   # "perplexity"
```

## Caveats
- This module only defines configuration and exports a `ChatModel` instance; it does not define any helper functions or invocation methods.
- Requires a valid `perplexity_api_key` available via `ABIModule` configuration.

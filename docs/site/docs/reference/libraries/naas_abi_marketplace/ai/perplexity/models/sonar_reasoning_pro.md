# `sonar_reasoning_pro`

## What it is
A module-level `ChatModel` instance configured for the Perplexity provider using LangChain’s `ChatPerplexity`, pre-set to the `sonar-reasoning-pro` model.

## Public API
- **Constants**
  - `MODEL_ID: str` — Set to `"sonar-reasoning-pro"`.
  - `PROVIDER: str` — Set to `"perplexity"`.

- **Objects**
  - `model: ChatModel` — A ready-to-use chat model wrapper:
    - Underlying model: `langchain_perplexity.ChatPerplexity`
    - Configuration:
      - `model="sonar-reasoning-pro"`
      - `temperature=0`
      - `timeout=120`
      - `api_key` loaded from `ABIModule.get_instance().configuration.perplexity_api_key` (wrapped in `pydantic.SecretStr`)

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_marketplace.ai.perplexity.ABIModule`
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`

- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set (Perplexity API key).

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar_reasoning_pro import model

# Use the configured ChatModel in your application.
# (Exact invocation depends on ChatModel's interface in naas_abi_core.)
print(model.model_id, model.provider)
```

## Caveats
- Importing this module initializes the underlying `ChatPerplexity` client immediately and reads the API key from `ABIModule` configuration.
- Temperature is fixed at `0` and timeout at `120` seconds in this definition.

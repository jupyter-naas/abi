# sonar

## What it is
A module-level `ChatModel` instance configured to use Perplexity’s `ChatPerplexity` chat model with the model id `"sonar"`.

## Public API
- **Constants**
  - `MODEL_ID: str` — Model identifier (`"sonar"`).
  - `PROVIDER: str` — Provider name (`"perplexity"`).
- **Objects**
  - `model: ChatModel` — Preconfigured chat model wrapper:
    - `model_id="sonar"`
    - `provider="perplexity"`
    - underlying `langchain_perplexity.ChatPerplexity` with:
      - `temperature=0`
      - `timeout=120`
      - `api_key` sourced from `ABIModule.get_instance().configuration.perplexity_api_key` (wrapped in `pydantic.SecretStr`)

## Configuration/Dependencies
- **Depends on**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_marketplace.ai.perplexity.ABIModule` (for configuration access)
  - `naas_abi_core.models.Model.ChatModel`
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set.

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar import model

# Use `model` wherever a `ChatModel` is expected in your application.
# (Exact invocation depends on `ChatModel`'s interface in naas_abi_core.)
print(model.model_id)     # "sonar"
print(model.provider)     # "perplexity"
```

## Caveats
- Importing this module constructs the `ChatPerplexity` client immediately; it requires `ABIModule` to be initialized and have `perplexity_api_key` available.

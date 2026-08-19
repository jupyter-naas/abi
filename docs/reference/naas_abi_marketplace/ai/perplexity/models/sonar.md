# sonar

## What it is
A module that exposes a preconfigured `ChatModel` instance (`model`) backed by Perplexity’s `ChatPerplexity` client using the `"sonar"` model.

## Public API
- **Constants**
  - `MODEL_ID: str` — Fixed model identifier: `"sonar"`.
  - `PROVIDER: str` — Fixed provider identifier: `"perplexity"`.
- **Objects**
  - `model: ChatModel` — A ready-to-use chat model wrapper configured with:
    - `model_id="sonar"`
    - `provider="perplexity"`
    - underlying `ChatPerplexity(model="sonar", temperature=0, timeout=120, api_key=SecretStr(...))`

## Configuration/Dependencies
- **Dependencies**
  - `langchain_perplexity.ChatPerplexity`
  - `naas_abi_core.models.Model.ChatModel`
  - `naas_abi_marketplace.ai.perplexity.ABIModule` (for configuration access)
  - `pydantic.SecretStr`
- **Required configuration**
  - `ABIModule.get_instance().configuration.perplexity_api_key` must be set (used to build `SecretStr(...)` for `api_key`).

## Usage
```python
from naas_abi_marketplace.ai.perplexity.models.sonar import model

print(model.model_id)   # sonar
print(model.provider)   # perplexity
```

## Caveats
- Importing this module instantiates `ChatPerplexity` immediately; it requires `ABIModule` to be available and configured with `perplexity_api_key` at import time.

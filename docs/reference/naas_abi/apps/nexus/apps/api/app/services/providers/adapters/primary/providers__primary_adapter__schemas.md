# providers__primary_adapter__schemas

## What it is
- Pydantic schema definitions and conversion helpers for representing providers and their models in the “primary” provider adapter.
- Converts internal provider domain objects (`ProviderInfo`, `ProviderModelInfo`) into API-facing Pydantic models.

## Public API
- **Classes**
  - `Model (pydantic.BaseModel)`: Schema for a single model offered by a provider.
    - Fields:
      - `id: str`
      - `name: str`
      - `provider: Literal["openai","anthropic","cloudflare","ollama","openrouter","xai","mistral","perplexity","google"]`
      - `context_window: int`
      - `supports_streaming: bool`
      - `supports_vision: bool`
      - `supports_function_calling: bool`
      - `max_output_tokens: int | None`
      - `released: str`
  - `Provider (pydantic.BaseModel)`: Schema for a provider and its available models.
    - Fields:
      - `id: str`
      - `name: str`
      - `type: Literal["openai","anthropic","cloudflare","ollama","openrouter","xai","mistral","perplexity","google"]`
      - `has_api_key: bool`
      - `logo_url: str | None = None`
      - `models: list[Model]`

- **Functions**
  - `to_model_schema(model: ProviderModelInfo) -> Model`
    - Maps a `ProviderModelInfo` instance into a `Model` schema.
  - `to_provider_schema(provider: ProviderInfo) -> Provider`
    - Maps a `ProviderInfo` instance into a `Provider` schema, including converting all nested models via `to_model_schema`.

## Configuration/Dependencies
- **Dependencies**
  - `pydantic.BaseModel`
  - `typing.Literal`
  - Internal types:
    - `ProviderInfo`
    - `ProviderModelInfo`
    - Imported from: `naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema`

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.primary.providers__primary_adapter__schemas import (
    to_provider_schema,
)

# provider_info must be an instance of ProviderInfo with a .models list of ProviderModelInfo
provider_schema = to_provider_schema(provider_info)

# Use as a Pydantic model (e.g., JSON for API responses)
print(provider_schema.model_dump())
```

## Caveats
- `provider` (on `Model`) and `type` (on `Provider`) are restricted to the declared `Literal` values; other values will fail Pydantic validation.
- `to_provider_schema` assumes `provider.models` is iterable and contains items compatible with `ProviderModelInfo` attributes used in `to_model_schema`.

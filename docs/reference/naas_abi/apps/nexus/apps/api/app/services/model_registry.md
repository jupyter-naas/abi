# model_registry

## What it is
Centralized, static registry of AI models grouped by provider. It exposes model metadata (capabilities and limits) and small helper functions to query models and provider assets (logos).

## Public API
### Types
- `ModelInfo (TypedDict)`
  - Model metadata fields:
    - `id: str`
    - `name: str`
    - `provider: Literal["openai","anthropic","cloudflare","ollama","openrouter","xai","mistral","perplexity","google"]`
    - `context_window: int`
    - `supports_streaming: bool`
    - `supports_vision: bool`
    - `supports_function_calling: bool`
    - `max_output_tokens: int | None`
    - `released: str` (format: `YYYY-MM-DD`)

### Constants
- `MODEL_REGISTRY: dict[str, list[ModelInfo]]`
  - Provider → list of `ModelInfo` entries.
- `PROVIDER_LOGOS: dict[str, str]`
  - Provider → local logo URL path (served from `/logos` endpoint).

### Functions
- `get_models_for_provider(provider: str) -> list[ModelInfo]`
  - Returns registered models for a provider (empty list if unknown).
- `get_all_models() -> list[ModelInfo]`
  - Returns a flattened list of all models across all providers.
- `get_model_by_id(model_id: str) -> ModelInfo | None`
  - Finds and returns the first model matching the given `id`, or `None` if not found.
- `get_all_provider_names() -> list[str]`
  - Returns provider names present in `MODEL_REGISTRY`.
- `get_logo_for_provider(provider: str) -> str | None`
  - Returns the default logo URL for a provider, or `None` if not found.

## Configuration/Dependencies
- No runtime configuration.
- Depends on Python typing utilities: `typing.Literal`, `typing.TypedDict`.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.model_registry import (
    get_all_provider_names,
    get_models_for_provider,
    get_model_by_id,
    get_logo_for_provider,
)

providers = get_all_provider_names()
print("Providers:", providers)

openai_models = get_models_for_provider("openai")
print("OpenAI model IDs:", [m["id"] for m in openai_models])

model = get_model_by_id("gpt-4o")
if model:
    print(model["name"], "vision:", model["supports_vision"])

print("OpenAI logo path:", get_logo_for_provider("openai"))
```

## Caveats
- The registry is static; it must be manually updated when providers release or deprecate models.
- `get_model_by_id()` matches by exact `id` string and returns the first match found.

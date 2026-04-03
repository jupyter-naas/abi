# model_registry

## What it is
A static **model registry**: a centralized catalog of AI models across multiple providers. It exposes metadata (capabilities, context window, etc.) and helper functions to query models and providers.

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
    - `released: str` (date string `YYYY-MM-DD`)

### Data
- `MODEL_REGISTRY: dict[str, list[ModelInfo]]`
  - Provider → list of registered `ModelInfo`.
- `PROVIDER_LOGOS: dict[str, str]`
  - Provider → local logo path (served from a `/logos` endpoint).

### Functions
- `get_models_for_provider(provider: str) -> list[ModelInfo]`
  - Returns all models registered for the given provider (or `[]` if unknown).
- `get_all_models() -> list[ModelInfo]`
  - Returns a flattened list of all models across all providers.
- `get_model_by_id(model_id: str) -> ModelInfo | None`
  - Finds a model by exact `id` across all providers (first match wins) or returns `None`.
- `get_all_provider_names() -> list[str]`
  - Returns all provider keys registered in `MODEL_REGISTRY`.
- `get_logo_for_provider(provider: str) -> str | None`
  - Returns the logo path for a provider or `None` if not defined.

## Configuration/Dependencies
- Depends only on the standard library: `typing` (`Literal`, `TypedDict`).
- Provider logos are stored as local URL paths (e.g. `"/logos/openai.jpg"`); serving those assets is handled elsewhere.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.model_registry import (
    get_all_provider_names,
    get_models_for_provider,
    get_model_by_id,
    get_logo_for_provider,
)

providers = get_all_provider_names()
print(providers)

openai_models = get_models_for_provider("openai")
print(openai_models[0]["id"], openai_models[0]["supports_vision"])

model = get_model_by_id("gpt-4o")
if model:
    print(model["provider"], model["context_window"])

print(get_logo_for_provider("anthropic"))
```

## Caveats
- Registry is **static**; models must be added/updated manually in `MODEL_REGISTRY`.
- `get_models_for_provider()` returns an empty list for unknown providers (no error).
- `get_model_by_id()` matches by exact string `id` and returns the first match across providers.

# providers__schema

## What it is
- A small schema module defining immutable (frozen) dataclasses and a provider type literal for describing LLM/AI providers and their models.

## Public API
- **`ProviderType`** (`typing.Literal[...]`)
  - Enumerates allowed provider identifiers:
    - `"openai"`, `"anthropic"`, `"cloudflare"`, `"ollama"`, `"openrouter"`, `"xai"`, `"mistral"`, `"perplexity"`, `"google"`.

- **`ProviderModelInfo`** (`@dataclass(frozen=True)`)
  - Describes a specific model offered by a provider.
  - Fields:
    - `id: str`
    - `name: str`
    - `provider: ProviderType`
    - `context_window: int`
    - `supports_streaming: bool`
    - `supports_vision: bool`
    - `supports_function_calling: bool`
    - `max_output_tokens: int | None`
    - `released: str`

- **`ProviderInfo`** (`@dataclass(frozen=True)`)
  - Describes a provider and its available models.
  - Fields:
    - `id: str`
    - `name: str`
    - `type: ProviderType`
    - `has_api_key: bool`
    - `logo_url: str | None`
    - `models: list[ProviderModelInfo]`

## Configuration/Dependencies
- Uses standard library only:
  - `dataclasses.dataclass`
  - `typing.Literal`
- Requires Python 3.10+ (for `| None` union syntax) and benefits from Python 3.11+ for `from __future__ import annotations` behavior.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema import (
    ProviderInfo,
    ProviderModelInfo,
)

model = ProviderModelInfo(
    id="gpt-4o-mini",
    name="GPT-4o mini",
    provider="openai",
    context_window=128000,
    supports_streaming=True,
    supports_vision=True,
    supports_function_calling=True,
    max_output_tokens=16384,
    released="2024-07-18",
)

provider = ProviderInfo(
    id="openai",
    name="OpenAI",
    type="openai",
    has_api_key=True,
    logo_url=None,
    models=[model],
)

print(provider.models[0].name)
```

## Caveats
- Instances are **immutable** (`frozen=True`); updating fields requires creating new instances.
- `ProviderType` is a `Literal`; type checkers will flag values outside the allowed set, but runtime does not enforce it beyond normal Python assignment.

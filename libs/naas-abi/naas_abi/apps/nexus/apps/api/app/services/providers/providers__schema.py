from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProviderType = Literal[
    "openai",
    "anthropic",
    "cloudflare",
    "ollama",
    "openrouter",
    "xai",
    "mistral",
    "perplexity",
    "google",
]


@dataclass(frozen=True)
class ProviderModelInfo:
    id: str
    name: str
    provider: ProviderType
    context_window: int
    supports_streaming: bool
    supports_vision: bool
    supports_function_calling: bool
    max_output_tokens: int | None
    released: str


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    name: str
    type: ProviderType
    has_api_key: bool
    logo_url: str | None
    models: list[ProviderModelInfo]

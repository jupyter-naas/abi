from __future__ import annotations

from typing import Literal

from naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema import (
    ProviderInfo,
    ProviderModelInfo,
)
from pydantic import BaseModel


class Model(BaseModel):
    id: str
    name: str
    provider: Literal[
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
    context_window: int
    supports_streaming: bool
    supports_vision: bool
    supports_function_calling: bool
    max_output_tokens: int | None
    released: str


class Provider(BaseModel):
    id: str
    name: str
    type: Literal[
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
    has_api_key: bool
    logo_url: str | None = None
    models: list[Model]


def to_model_schema(model: ProviderModelInfo) -> Model:
    return Model(
        id=model.id,
        name=model.name,
        provider=model.provider,
        context_window=model.context_window,
        supports_streaming=model.supports_streaming,
        supports_vision=model.supports_vision,
        supports_function_calling=model.supports_function_calling,
        max_output_tokens=model.max_output_tokens,
        released=model.released,
    )


def to_provider_schema(provider: ProviderInfo) -> Provider:
    return Provider(
        id=provider.id,
        name=provider.name,
        type=provider.type,
        has_api_key=provider.has_api_key,
        logo_url=provider.logo_url,
        models=[to_model_schema(model) for model in provider.models],
    )

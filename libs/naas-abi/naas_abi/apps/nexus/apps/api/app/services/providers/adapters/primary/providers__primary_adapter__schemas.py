from __future__ import annotations

import os

from naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema import (
    ProviderInfo,
    ProviderModelInfo,
)
from pydantic import BaseModel

# Env vars that mean "this provider can actually be called", even when the
# marketplace module is not loaded (Zen local-first often keeps cloud modules
# disabled). Used for Nexus chat model picker compatibility fields.
_PROVIDER_API_KEY_ENV: dict[str, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "chatgpt": "OPENAI_API_KEY",
    "xai": "XAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "google": "GOOGLE_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
}


def _env_has_api_key(provider_id: str) -> bool:
    if provider_id == "ollama":
        return True
    env_name = _PROVIDER_API_KEY_ENV.get(provider_id)
    if not env_name:
        return False
    value = (os.environ.get(env_name) or "").strip()
    if value:
        return True
    try:
        from naas_abi import ABIModule

        secret_value = ABIModule.get_instance().engine.services.secret.get(env_name)
        return bool(secret_value and str(secret_value).strip())
    except Exception:
        return False


class Model(BaseModel):
    canonical_id: str
    model_id: str
    provider: str
    provider_id: str
    module_path: str
    configured: bool
    name: str | None = None
    description: str | None = None
    image: str | None = None
    context_window: int | None = None
    # Frontend chat picker expects ``id`` (alias of model_id).
    id: str | None = None


class ModelUpdate(BaseModel):
    """Body for ``PATCH /api/providers/models/{model_id}``.

    Only the fields actually present in the request are applied (and recorded as
    frontend overrides); use ``model_dump(exclude_unset=True)`` to read them.
    """

    name: str | None = None
    description: str | None = None
    image: str | None = None
    context_window: int | None = None


class Provider(BaseModel):
    id: str
    name: str
    module_path: str
    configured: bool
    logo_url: str | None = None
    config_keys: list[str] = []
    models: list[Model] = []
    description: str | None = None
    tags: list[str] = []
    slug: str | None = None
    privacy_policy_url: str | None = None
    terms_of_service_url: str | None = None
    status_page_url: str | None = None
    headquarters: str | None = None
    datacenters: list[str] | None = None
    # Frontend integrations / agent picker compatibility fields.
    type: str | None = None
    has_api_key: bool = False


def to_model_schema(model: ProviderModelInfo) -> Model:
    return Model(
        canonical_id=model.canonical_id,
        model_id=model.model_id,
        provider=model.provider,
        provider_id=model.provider_id,
        module_path=model.module_path,
        configured=model.configured,
        name=model.name,
        description=model.description,
        image=model.image,
        context_window=model.context_window,
        id=model.model_id,
    )


def to_provider_schema(provider: ProviderInfo) -> Provider:
    has_key = bool(provider.configured) or _env_has_api_key(provider.id)
    return Provider(
        id=provider.id,
        name=provider.name,
        module_path=provider.module_path,
        configured=provider.configured,
        logo_url=provider.logo_url,
        config_keys=list(provider.config_keys),
        models=[to_model_schema(model) for model in provider.models],
        description=provider.description,
        tags=list(provider.tags),
        slug=provider.slug,
        privacy_policy_url=provider.privacy_policy_url,
        terms_of_service_url=provider.terms_of_service_url,
        status_page_url=provider.status_page_url,
        headquarters=provider.headquarters,
        datacenters=list(provider.datacenters) if provider.datacenters is not None else None,
        type=provider.id,
        has_api_key=has_key,
    )

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema import (
    ProviderInfo,
    ProviderModelInfo,
)
from pydantic import BaseModel


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
    )


def to_provider_schema(provider: ProviderInfo) -> Provider:
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
    )

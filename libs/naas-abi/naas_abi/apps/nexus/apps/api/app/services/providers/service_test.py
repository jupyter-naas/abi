from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.providers.service import ProviderService


@pytest.mark.asyncio
async def test_list_available_providers_returns_full_marketplace_catalog() -> None:
    """Every naas_abi_marketplace.ai.* module shows up regardless of secrets."""
    service = ProviderService()

    providers = await service.list_available_providers()

    provider_ids = {p.id for p in providers}
    assert {"chatgpt", "anthropic", "openrouter"} <= provider_ids


@pytest.mark.asyncio
async def test_unconfigured_providers_are_marked_not_configured() -> None:
    service = ProviderService()

    providers = await service.list_available_providers()

    # In a unit-test process the engine has no marketplace modules loaded, so
    # every provider should be flagged not configured. Their models inherit
    # that flag.
    for provider in providers:
        assert provider.configured is False
        for model in provider.models:
            assert model.configured is False


@pytest.mark.asyncio
async def test_providers_carry_abimodule_metadata() -> None:
    """Provider display metadata is read from each provider's ABIModule class."""
    service = ProviderService()

    providers = await service.list_available_providers()
    by_id = {p.id: p for p in providers}

    openai = by_id["openai"]
    assert openai.name == "OpenAI"
    assert openai.logo_url == (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/openai.png"
    )
    assert "gpt" in openai.tags
    assert openai.slug == "openai"
    # No marketplace AI module currently declares location metadata, so these
    # fields fall back to their dataclass default of None.
    assert openai.headquarters is None
    assert openai.datacenters is None

    openrouter = by_id["openrouter"]
    assert openrouter.name == "OpenRouter"
    assert "api gateway" in openrouter.tags
    # Fields absent from the ABIModule class default to None.
    assert openrouter.headquarters is None


@pytest.mark.asyncio
async def test_local_logo_served_via_public_route() -> None:
    """A module-relative logo_url is rewritten to the public logo route, while
    remote http logos pass through verbatim."""
    service = ProviderService()

    providers = await service.list_available_providers()
    by_id = {p.id: p for p in providers}

    # openrouter ships a local asset under its module dir.
    assert by_id["openrouter"].logo_url == "/provider-logos/openrouter"
    # openai declares a remote S3 URL — kept as-is.
    assert by_id["openai"].logo_url == (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/openai.png"
    )


def test_resolve_provider_logo_for_id_finds_file_on_disk() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
        resolve_provider_logo_for_id,
    )

    path = resolve_provider_logo_for_id("openrouter")
    assert path is not None
    assert path.is_file()
    assert path.name == "openrouter.jpg"


@pytest.mark.asyncio
async def test_list_models_returns_models_across_providers() -> None:
    service = ProviderService()

    models = await service.list_models()

    assert len(models) > 0
    provider_ids = {m.provider_id for m in models}
    assert {"chatgpt", "anthropic"} <= provider_ids


@pytest.mark.asyncio
async def test_get_model_finds_by_canonical_or_provider_id() -> None:
    service = ProviderService()

    models = await service.list_models()
    assert models, "expected at least one catalog model"
    sample = models[0]

    by_canonical = await service.get_model(canonical_or_model_id=sample.canonical_id)
    assert by_canonical is not None
    assert by_canonical.canonical_id == sample.canonical_id


@pytest.mark.asyncio
async def test_get_model_returns_none_for_unknown_id() -> None:
    service = ProviderService()

    result = await service.get_model(canonical_or_model_id="not-a-real-model-id")
    assert result is None

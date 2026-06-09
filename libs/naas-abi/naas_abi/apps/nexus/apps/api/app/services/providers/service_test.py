from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.providers.service import ProviderService


@pytest.mark.asyncio
async def test_list_available_providers_returns_full_marketplace_catalog() -> None:
    """Every naas_abi_marketplace.ai.* module shows up regardless of secrets."""
    service = ProviderService()

    providers = await service.list_available_providers()

    provider_ids = {p.id for p in providers}
    assert {"chatgpt", "claude", "openrouter"} <= provider_ids


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
async def test_list_models_returns_models_across_providers() -> None:
    service = ProviderService()

    models = await service.list_models()

    assert len(models) > 0
    provider_ids = {m.provider_id for m in models}
    assert {"chatgpt", "claude"} <= provider_ids


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

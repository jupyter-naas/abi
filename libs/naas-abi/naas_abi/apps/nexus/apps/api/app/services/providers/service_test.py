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
    """Provider display metadata is read from each provider's ABIModule class.

    Asserts structure (names, slugs, tags, logo shape) rather than the exact
    logo URLs, which are data the marketplace modules edit freely.
    """
    service = ProviderService()

    providers = await service.list_available_providers()
    by_id = {p.id: p for p in providers}

    openai = by_id["openai"]
    assert openai.name == "OpenAI"
    assert openai.slug == "openai"
    assert "gpt" in openai.tags
    assert openai.logo_url and openai.logo_url.startswith("http")
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
async def test_remote_logo_passes_through_verbatim() -> None:
    """A provider declaring a remote http(s) logo serves it unchanged."""
    service = ProviderService()

    providers = await service.list_available_providers()
    by_id = {p.id: p for p in providers}

    # openai/openrouter currently declare remote URLs in their ABIModule class.
    for pid in ("openai", "openrouter"):
        logo = by_id[pid].logo_url
        assert logo is not None and logo.startswith("http")
        # No /provider-logos rewrite for remote URLs.
        assert "/provider-logos/" not in logo


def test_local_logo_url_is_rewritten_to_public_route() -> None:
    """A module-relative logo_url resolves to the public /provider-logos route.

    Driven by a synthetic catalog entry so it stays valid regardless of which
    URL each marketplace module currently declares.
    """
    from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
        ProviderCatalogEntry,
    )
    from naas_abi.apps.nexus.apps.api.app.services.providers.service import (
        _provider_logo_url,
    )

    entry = ProviderCatalogEntry(
        provider_id="openrouter",
        module_path="naas_abi_marketplace.ai.openrouter",
        config_keys=(),
        logo_url="openrouter/assets/public/openrouter.jpg",
    )
    # In a unit-test process the ABIModule isn't initialized, so the URL is the
    # relative public route (no public_api_host prefix).
    assert _provider_logo_url(entry) == "/provider-logos/openrouter"


def test_resolve_provider_logo_file_finds_asset_on_disk() -> None:
    """The bundled openrouter asset resolves to a real file on disk."""
    from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
        resolve_provider_logo_file,
    )

    path = resolve_provider_logo_file("openrouter", "openrouter/assets/public/openrouter.jpg")
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


# ---------------------------------------------------------------------------
# Model catalog store: sync + frontend override behaviour
# ---------------------------------------------------------------------------


def _make_entry(canonical_id: str = "m1", **overrides):
    from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
        ModelCatalogEntry,
    )

    defaults = {
        "canonical_id": canonical_id,
        "model_id": "anthropic/m1",
        "provider": "anthropic",
        "provider_id": "anthropic",
        "module_path": "naas_abi_marketplace.ai.anthropic",
        "file": "m1.py",
        "name": "Original Name",
        "description": "Original description",
        "image": None,
        "context_window": 1000,
    }
    defaults.update(overrides)
    return ModelCatalogEntry(**defaults)


class _FakeStore:
    """In-memory ModelCatalogStorePort for unit tests."""

    def __init__(self) -> None:
        self.rows: dict = {}

    async def list_all(self):
        import copy

        return [copy.deepcopy(r) for r in self.rows.values()]

    async def get(self, canonical_id):
        import copy

        row = self.rows.get(canonical_id)
        return copy.deepcopy(row) if row else None

    async def upsert(self, record):
        import copy

        self.rows[record.canonical_id] = copy.deepcopy(record)
        return copy.deepcopy(record)


def test_reconcile_seeds_source_baseline_for_new_model() -> None:
    service = ProviderService()
    record, warnings = service._reconcile(_make_entry(), None)

    assert warnings == []
    assert record.name == "Original Name"
    assert record.source_name == "Original Name"
    assert record.overridden_fields == []


def test_reconcile_follows_source_when_not_overridden() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.providers.port import StoredModel

    service = ProviderService()
    prev = StoredModel(
        canonical_id="m1",
        model_id="anthropic/m1",
        provider="anthropic",
        provider_id="anthropic",
        module_path="naas_abi_marketplace.ai.anthropic",
        name="Original description-less",
        description="old",
        source_description="old",
        overridden_fields=[],
    )
    record, warnings = service._reconcile(_make_entry(description="new from code"), prev)

    assert record.description == "new from code"
    assert record.source_description == "new from code"
    assert warnings == []


def test_reconcile_keeps_override_and_warns_on_source_change() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.providers.port import StoredModel

    service = ProviderService()
    prev = StoredModel(
        canonical_id="m1",
        model_id="anthropic/m1",
        provider="anthropic",
        provider_id="anthropic",
        module_path="naas_abi_marketplace.ai.anthropic",
        description="USER EDITED",
        source_description="Original description",
        overridden_fields=["description"],
    )
    record, warnings = service._reconcile(_make_entry(description="NEW SOURCE"), prev)

    # Frontend value preserved; source advanced; one warning emitted.
    assert record.description == "USER EDITED"
    assert record.source_description == "NEW SOURCE"
    assert len(warnings) == 1
    assert "m1" in warnings[0] and "description" in warnings[0]


@pytest.mark.asyncio
async def test_update_model_persists_override_and_overlays_served_value() -> None:
    store = _FakeStore()
    service = ProviderService(store=store)

    models = await service.list_models()
    sample = models[0]

    updated = await service.update_model(sample.canonical_id, {"description": "Edited!"})
    assert updated is not None
    assert updated.description == "Edited!"

    # The override is reflected on subsequent reads...
    served = await service.get_model(sample.canonical_id)
    assert served is not None and served.description == "Edited!"

    # ...and the stored row records it as overridden.
    row = await store.get(sample.canonical_id)
    assert row is not None and "description" in row.overridden_fields


@pytest.mark.asyncio
async def test_sync_preserves_frontend_override_and_warns() -> None:
    store = _FakeStore()
    service = ProviderService(store=store)

    await service.sync_models()
    sample = (await service.list_models())[0]

    await service.update_model(sample.canonical_id, {"description": "Manual override"})

    # Simulate the Python source description drifting from what was recorded.
    row = await store.get(sample.canonical_id)
    row.source_description = "stale-old-source"
    await store.upsert(row)

    warnings = await service.sync_models()

    served = await service.get_model(sample.canonical_id)
    assert served is not None and served.description == "Manual override"
    assert any(sample.canonical_id in w and "description" in w for w in warnings)

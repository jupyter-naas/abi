from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core import config
from naas_abi.apps.nexus.apps.api.app.core.config import TenantConfig
from naas_abi.apps.nexus.apps.api.app.services.tenant import TenantService


@pytest.mark.asyncio
async def test_the_tenant_names_the_site(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config.settings, "tenant", TenantConfig(name="Acme Portal", tab_title="Acme")
    )
    tenant = await TenantService.get_tenant_config()
    assert (tenant.name, tenant.tab_title) == ("Acme Portal", "Acme")


@pytest.mark.asyncio
async def test_without_a_name_the_tenant_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "tenant", TenantConfig())
    assert (await TenantService.get_tenant_config()).name is None


def test_the_module_configuration_accepts_a_name() -> None:
    from naas_abi import TenantConfig as ModuleTenantConfig

    assert ModuleTenantConfig(name="Acme Portal").name == "Acme Portal"


@pytest.mark.asyncio
async def test_the_tenant_carries_the_login_heading_logo_size_and_footer_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        config.settings,
        "tenant",
        TenantConfig(
            login_heading="Acme Platform",
            logo_height=96,
            login_footer_link_label="Grant 123",
            login_footer_link_url="https://example.org/grant/123",
        ),
    )
    tenant = await TenantService.get_tenant_config()
    assert (
        tenant.login_heading,
        tenant.logo_height,
        tenant.login_footer_link_label,
        tenant.login_footer_link_url,
    ) == ("Acme Platform", 96, "Grant 123", "https://example.org/grant/123")


@pytest.mark.asyncio
async def test_by_default_the_login_keeps_the_typewriter_and_48px_logo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.settings, "tenant", TenantConfig())
    tenant = await TenantService.get_tenant_config()
    assert (tenant.login_heading, tenant.logo_height, tenant.login_footer_link_url) == (
        None,
        48,
        None,
    )


def test_the_module_configuration_accepts_the_login_fields() -> None:
    from naas_abi import TenantConfig as ModuleTenantConfig

    module_tenant = ModuleTenantConfig(login_heading="Acme Platform", logo_height=96)
    assert (module_tenant.login_heading, module_tenant.logo_height) == ("Acme Platform", 96)

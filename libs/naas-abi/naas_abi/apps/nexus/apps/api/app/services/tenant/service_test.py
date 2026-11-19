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

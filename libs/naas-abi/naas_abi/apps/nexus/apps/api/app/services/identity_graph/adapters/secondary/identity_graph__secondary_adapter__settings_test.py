from __future__ import annotations

import datetime

from naas_abi.apps.nexus.apps.api.app.core.config import Settings
from naas_abi.apps.nexus.apps.api.app.services.identity_graph.adapters.secondary.identity_graph__secondary_adapter__settings import (  # noqa: E501
    PlatformConfigurationSourceSettings,
    flatten_settings,
)
from pydantic import BaseModel

BOOT = datetime.datetime(2026, 9, 10, 8, 0)


class _ModuleConfig(BaseModel):
    abi_agent_model: str = "qwen-3.8"
    abi_slides_agent_model: str = "qwen-3.8"
    ontology_engineer_model: str = "qwen-3.8"
    abi_agent_provider: str | None = None
    nexus_config: dict = {}


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://nexus:s3cr3t-pw@postgres:5432/nexus",
        secret_key="k" * 40,
        frontend_url="https://bob.example.com",
        magic_link_allow_signup=False,
        magic_link_email_app_name="BOB Platform",
        tenant={
            "tab_title": "Bob AI Platform",
            "primary_color": "#0057B8",
            "show_powered_by": False,
        },
        feature_flags={
            "enabled_features": ["chat", "slides"],
            "role_baseline": {"owner": ["chat", "slides"], "viewer": ["chat"]},
            "workspace_overrides": {"adqcc": {"agents": False}},
        },
        users=[
            {"email": "alice@example.com", "name": "Alice", "store_credentials_in_secrets": False},
            {"email": "Bob@Example.com", "name": "Bob"},
        ],
        organizations=[
            {
                "name": "Acme",
                "slug": "acme",
                "workspaces": [
                    {
                        "name": "ADQCC",
                        "slug": "adqcc",
                        "default_agent": "external.adqcc AdqccAgent",
                        "agents": ["external.adqcc AdqccAgent", "bob BobAgent"],
                        "apps": ["external.adqcc:web"],
                        "ontologies": ["adqcc:AdqccOntology.ttl"],
                    }
                ],
            }
        ],
    )


def _load(settings: Settings | None = None):
    source = PlatformConfigurationSourceSettings(
        settings_getter=lambda: settings or _settings(),
        module_config_getter=lambda: _ModuleConfig(),
        clock=lambda: BOOT,
    )
    return source.load_platform()


def test_host_comes_from_the_public_frontend_url() -> None:
    platform = _load()
    assert platform.host == "bob.example.com"
    assert platform.applied_at == BOOT


def test_secrets_never_reach_the_graph() -> None:
    platform = _load()

    assert "nexus_config.database_url" not in platform.settings
    assert "nexus_config.secret_key" not in platform.settings
    assert not any("s3cr3t" in value for value in platform.settings.values())
    assert not any(key.endswith("secret") or "password" in key for key in platform.settings)


def test_module_and_nexus_settings_are_flattened() -> None:
    platform = _load()

    assert platform.settings["abi_agent_model"] == "qwen-3.8"
    assert platform.settings["nexus_config.magic_link_allow_signup"] == "false"
    assert platform.settings["nexus_config.magic_link_email_app_name"] == "BOB Platform"
    # Typed sections are modelled as their own classes, not as settings.
    assert not any(
        k.startswith(("nexus_config.users", "nexus_config.organizations"))
        for k in platform.settings
    )
    assert not any(
        k.startswith(("nexus_config.feature_flags", "nexus_config.tenant"))
        for k in platform.settings
    )


def test_feature_flags_tenant_and_seeds_are_typed() -> None:
    platform = _load()

    assert platform.enabled_features == ["chat", "slides"]
    assert platform.role_baseline["viewer"] == ["chat"]
    assert platform.workspace_overrides == {"adqcc": {"agents": False}}
    assert platform.tenant["tab_title"] == "Bob AI Platform"
    assert platform.credential_storage_by_email == {
        "alice@example.com": False,
        "bob@example.com": True,
    }
    seed = platform.workspace_seeds["adqcc"]
    assert seed.default_agent == "external.adqcc AdqccAgent"
    assert seed.agents == ["external.adqcc AdqccAgent", "bob BobAgent"]
    assert seed.apps == ["external.adqcc:web"]
    assert seed.ontologies == ["adqcc:AdqccOntology.ttl"]


def test_urls_carrying_credentials_are_stripped_even_under_innocent_keys() -> None:
    flat = flatten_settings(
        {"mirror": "https://user:hunter2@example.com/repo.git", "plain": "https://example.com"}
    )

    assert flat["mirror"] == "https://example.com/repo.git"
    assert flat["plain"] == "https://example.com"


def test_unavailable_configuration_yields_nothing() -> None:
    def boom():
        raise RuntimeError("not loaded")

    source = PlatformConfigurationSourceSettings(settings_getter=boom, module_config_getter=boom)
    assert source.load_platform() is None

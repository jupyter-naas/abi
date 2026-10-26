from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import (
    effective_seed_agents,
    effective_seed_default_agent,
)


def test_catalog_seed_overrides_yaml_agents() -> None:
    catalog = {"agents": ["external.acme AcmeAgent"], "default_agent": "external.acme AcmeAgent"}
    assert effective_seed_agents("klepierre", catalog) == ["external.acme AcmeAgent"]
    assert effective_seed_default_agent("klepierre", catalog) == "external.acme AcmeAgent"


def test_empty_catalog_agents_list_is_explicit() -> None:
    assert effective_seed_agents("x", {"agents": []}) == []

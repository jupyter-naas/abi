from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    parse_agent_ref,
    resolve_agent_ref,
    resolve_agent_refs,
    resolve_app_enabled,
)


def test_parse_agent_ref() -> None:
    assert parse_agent_ref("naas_abi AbiAgent") == ("naas_abi", "AbiAgent")
    assert parse_agent_ref("naas_abi SlidesAgent") == ("naas_abi", "SlidesAgent")
    assert parse_agent_ref("example.module ExampleAgent") == (
        "example.module",
        "ExampleAgent",
    )
    assert parse_agent_ref("AbiAgent") is None
    assert parse_agent_ref("") is None


def test_resolve_agent_ref_prefers_module_prefix() -> None:
    registry = {
        "naas_abi.agents.AbiAgent/AbiAgent": object(),
        "naas_abi.agents.SlidesAgent/SlidesAgent": object(),
        "example.module.agents.ExampleAgent/ExampleAgent": object(),
    }
    assert (
        resolve_agent_ref("naas_abi AbiAgent", registry)
        == "naas_abi.agents.AbiAgent/AbiAgent"
    )
    assert (
        resolve_agent_ref("naas_abi SlidesAgent", registry)
        == "naas_abi.agents.SlidesAgent/SlidesAgent"
    )
    assert (
        resolve_agent_ref("example.module ExampleAgent", registry)
        == "example.module.agents.ExampleAgent/ExampleAgent"
    )
    assert resolve_agent_ref("missing Agent", registry) is None


def test_resolve_agent_refs_skips_unknown() -> None:
    registry = {"naas_abi.agents.AbiAgent/AbiAgent": object()}
    assert resolve_agent_refs(
        ["naas_abi AbiAgent", "nope NopeAgent"], registry
    ) == {"naas_abi.agents.AbiAgent/AbiAgent"}


def test_resolve_app_enabled_prefers_db_then_seed() -> None:
    seed = {"example.module:dashboard"}
    stored = {"example.module:dashboard": False, "example.module:other": True}
    assert resolve_app_enabled("example.module:dashboard", stored, seed) is False
    assert resolve_app_enabled("example.module:other", stored, seed) is True
    assert resolve_app_enabled("example.module:dashboard", {}, seed) is True
    assert resolve_app_enabled("example.module:unknown", {}, seed) is False

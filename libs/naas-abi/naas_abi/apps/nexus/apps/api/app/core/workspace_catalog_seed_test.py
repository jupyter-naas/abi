from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    filter_ontology_catalog,
    ontology_matches_seed,
    parse_agent_ref,
    resolve_agent_ref,
    resolve_agent_refs,
    resolve_app_enabled,
)


def test_parse_agent_ref() -> None:
    assert parse_agent_ref("naas_abi AbiAgent") == ("naas_abi", "AbiAgent")
    assert parse_agent_ref("example.module ExampleAgent") == (
        "example.module",
        "ExampleAgent",
    )
    assert parse_agent_ref("AbiAgent") is None
    assert parse_agent_ref("") is None


def test_resolve_agent_ref_prefers_module_prefix() -> None:
    registry = {
        "naas_abi.agents.AbiAgent/AbiAgent": object(),
        "example.module.agents.ExampleAgent/ExampleAgent": object(),
    }
    assert (
        resolve_agent_ref("naas_abi AbiAgent", registry)
        == "naas_abi.agents.AbiAgent/AbiAgent"
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


def test_ontology_matches_seed_module_filename() -> None:
    path = "/repo/src/example/ontologies/modules/ExampleOntology.ttl"
    assert ontology_matches_seed(path, "example", ["example:ExampleOntology.ttl"]) is True
    assert ontology_matches_seed(path, "example", ["bfo:bfo-core.ttl"]) is False


def test_ontology_matches_seed_does_not_expand_imports() -> None:
    bfo = "/repo/libs/naas-abi-core/naas_abi_core/modules/bfo/ontologies/modules/bfo-core.ttl"
    assert ontology_matches_seed(bfo, "bfo", ["example:ExampleOntology.ttl"]) is False


def test_filter_ontology_catalog_none_keeps_all() -> None:
    items = [
        SimpleNamespace(path="/a/ontologies/modules/A.ttl", module_name="a"),
        SimpleNamespace(path="/b/ontologies/modules/B.ttl", module_name="b"),
    ]
    assert filter_ontology_catalog(items, None) == items


def test_filter_ontology_catalog_empty_list_is_none() -> None:
    items = [SimpleNamespace(path="/a/ontologies/modules/A.ttl", module_name="a")]
    assert filter_ontology_catalog(items, []) == []


def test_filter_ontology_catalog_exclusive_list() -> None:
    example = SimpleNamespace(
        path="/repo/src/example/ontologies/modules/ExampleOntology.ttl",
        module_name="example",
    )
    bfo = SimpleNamespace(
        path="/repo/libs/naas-abi-core/naas_abi_core/modules/bfo/ontologies/modules/bfo-core.ttl",
        module_name="bfo",
    )
    cco = SimpleNamespace(
        path="/repo/libs/naas-abi-core/naas_abi_core/modules/cco/ontologies/modules/AgentOntology.ttl",
        module_name="cco",
    )
    filtered = filter_ontology_catalog(
        [example, bfo, cco],
        ["example:ExampleOntology.ttl", "bfo:bfo-core.ttl"],
    )
    assert filtered == [example, bfo]


def test_workspace_seed_config_accepts_ontologies() -> None:
    from naas_abi.apps.nexus.apps.api.app.core.config import WorkspaceSeedConfig

    seed = WorkspaceSeedConfig(
        name="Example",
        slug="example",
        ontologies=["example:ExampleOntology.ttl", "bfo:bfo-core.ttl"],
    )
    assert seed.ontologies == ["example:ExampleOntology.ttl", "bfo:bfo-core.ttl"]
    assert WorkspaceSeedConfig(name="Example", slug="example").ontologies is None

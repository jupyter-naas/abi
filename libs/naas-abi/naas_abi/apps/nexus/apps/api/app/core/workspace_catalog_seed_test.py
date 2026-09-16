from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    OntologyCatalogScope,
    filter_ontology_catalog,
    ontology_catalog_id,
    ontology_config_lookup_ids,
    ontology_matches_seed,
    parse_agent_ref,
    resolve_agent_ref,
    resolve_agent_refs,
    resolve_app_enabled,
    resolve_ontology_enabled,
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


EXAMPLE = SimpleNamespace(
    path="/repo/src/example/ontologies/modules/ExampleOntology.ttl",
    module_name="example",
)
BFO = SimpleNamespace(
    path="/repo/libs/naas-abi-core/naas_abi_core/modules/bfo/ontologies/modules/bfo-core.ttl",
    module_name="bfo",
)
CCO = SimpleNamespace(
    path="/repo/libs/naas-abi-core/naas_abi_core/modules/cco/ontologies/modules/AgentOntology.ttl",
    module_name="cco",
)


def test_ontology_catalog_id_is_module_and_filename() -> None:
    assert ontology_catalog_id(EXAMPLE.path, "example") == "example:exampleontology.ttl"
    assert ontology_catalog_id(BFO.path, "bfo") == "bfo:bfo-core.ttl"
    # Module names reach us space-separated (``naas abi`` from the catalog scan).
    assert ontology_catalog_id("/x/ontologies/modules/A.ttl", "naas abi") == "naas_abi:a.ttl"


def test_ontology_catalog_id_is_path_independent() -> None:
    """A row keyed here must survive the container/checkout path difference."""
    container = "/app/libs/naas-abi-core/naas_abi_core/modules/bfo/ontologies/modules/bfo-core.ttl"
    assert ontology_catalog_id(container, "bfo") == ontology_catalog_id(BFO.path, "bfo")


def test_ontology_config_lookup_ids_puts_canonical_first() -> None:
    ids = ontology_config_lookup_ids(BFO.path, "bfo")
    assert ids[0] == "bfo:bfo-core.ttl"
    # Seed-written aliases are still recognised.
    assert "bfo-core.ttl" in ids
    assert BFO.path in ids


def test_resolve_ontology_enabled_defaults_to_disabled() -> None:
    assert resolve_ontology_enabled(EXAMPLE.path, "example", {}, None) is False
    assert resolve_ontology_enabled(EXAMPLE.path, "example", {}, []) is False


def test_resolve_ontology_enabled_prefers_db_then_seed() -> None:
    seed = ["example:ExampleOntology.ttl", "bfo:bfo-core.ttl"]
    stored = {"example:exampleontology.ttl": False}
    # DB row wins over the seed list...
    assert resolve_ontology_enabled(EXAMPLE.path, "example", stored, seed) is False
    # ...and the seed only applies where no row exists.
    assert resolve_ontology_enabled(BFO.path, "bfo", stored, seed) is True
    assert resolve_ontology_enabled(CCO.path, "cco", stored, seed) is False


def test_resolve_ontology_enabled_matches_seed_written_alias_rows() -> None:
    """``_seed_workspace_ontologies`` stores whatever form the YAML used."""
    assert resolve_ontology_enabled(BFO.path, "bfo", {"bfo-core.ttl": True}, None) is True
    assert resolve_ontology_enabled(BFO.path, "bfo", {BFO.path: True}, None) is True


def test_filter_ontology_catalog_none_keeps_all() -> None:
    """No workspace context: nothing to resolve against, keep the engine listing."""
    items = [
        SimpleNamespace(path="/a/ontologies/modules/A.ttl", module_name="a"),
        SimpleNamespace(path="/b/ontologies/modules/B.ttl", module_name="b"),
    ]
    assert filter_ontology_catalog(items, None) == items


def test_filter_ontology_catalog_empty_scope_shows_nothing() -> None:
    """Fresh workspace: no rows and no seed means no ontologies at all."""
    items = [EXAMPLE, BFO, CCO]
    assert filter_ontology_catalog(items, OntologyCatalogScope()) == []


def test_filter_ontology_catalog_seed_pre_enables() -> None:
    scope = OntologyCatalogScope(
        seed_refs=("example:ExampleOntology.ttl", "bfo:bfo-core.ttl"),
    )
    assert filter_ontology_catalog([EXAMPLE, BFO, CCO], scope) == [EXAMPLE, BFO]


def test_filter_ontology_catalog_stored_row_overrides_seed() -> None:
    scope = OntologyCatalogScope(
        enabled_by_id={"bfo:bfo-core.ttl": False, "cco:agentontology.ttl": True},
        seed_refs=("example:ExampleOntology.ttl", "bfo:bfo-core.ttl"),
    )
    assert filter_ontology_catalog([EXAMPLE, BFO, CCO], scope) == [EXAMPLE, CCO]


def test_workspace_seed_config_accepts_ontologies() -> None:
    from naas_abi.apps.nexus.apps.api.app.core.config import WorkspaceSeedConfig

    seed = WorkspaceSeedConfig(
        name="Example",
        slug="example",
        ontologies=["example:ExampleOntology.ttl", "bfo:bfo-core.ttl"],
    )
    assert seed.ontologies == ["example:ExampleOntology.ttl", "bfo:bfo-core.ttl"]
    assert WorkspaceSeedConfig(name="Example", slug="example").ontologies is None

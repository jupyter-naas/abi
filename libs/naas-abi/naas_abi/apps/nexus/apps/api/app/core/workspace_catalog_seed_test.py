from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    filter_ontology_catalog,
    ontology_matches_seed,
    parse_agent_ref,
    resolve_agent_ref,
    resolve_agent_refs,
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
    assert resolve_agent_ref("naas_abi AbiAgent", registry) == "naas_abi.agents.AbiAgent/AbiAgent"
    assert (
        resolve_agent_ref("example.module ExampleAgent", registry)
        == "example.module.agents.ExampleAgent/ExampleAgent"
    )
    assert resolve_agent_ref("missing Agent", registry) is None


def test_resolve_agent_refs_skips_unknown() -> None:
    registry = {"naas_abi.agents.AbiAgent/AbiAgent": object()}
    assert resolve_agent_refs(["naas_abi AbiAgent", "nope NopeAgent"], registry) == {
        "naas_abi.agents.AbiAgent/AbiAgent"
    }


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
    assert WorkspaceSeedConfig(name="Example", slug="example").ontologies == []


def test_ontology_refs_do_not_match_partial_names_or_paths() -> None:
    path = "/repo/src/example/ontologies/modules/PrivateExample.ttl"
    assert not ontology_matches_seed(path, "example", ["Example.ttl"])
    assert not ontology_matches_seed(
        path, "example", ["ample/ontologies/modules/PrivateExample.ttl"]
    )
    assert not ontology_matches_seed(path, "example", ["/modules/PrivateExample.ttl"])
    assert ontology_matches_seed(path, "example", ["example/ontologies/modules/PrivateExample.ttl"])
    assert ontology_matches_seed(path, "example", [path])


def test_a_remote_ontology_is_not_admitted_by_a_bare_file_name_or_a_path_suffix() -> None:
    evil = "module/evil/modules/FooOntology.ttl"
    for ref in (
        "FooOntology.ttl",
        "fooontology.ttl",
        "modules/FooOntology.ttl",
        "naas_abi:FooOntology.ttl",
        "other.module:FooOntology.ttl",
    ):
        assert ontology_matches_seed(evil, "evil", [ref]) is False, ref
    assert ontology_matches_seed("module/evil/Foo.ttl", "evil", ["Foo.ttl"]) is False
    items = [SimpleNamespace(path="module/evil/Foo.ttl", module_name="evil")]
    assert filter_ontology_catalog(items, ["Foo.ttl"]) == []


def test_a_remote_ontology_matches_its_full_id_and_its_modules_file_ref() -> None:
    path = "module/acme.foo/domain/Review.ttl"
    assert ontology_matches_seed(path, "acme.foo", [path]) is True
    assert ontology_matches_seed(path, "acme.foo", ["acme.foo:Review.ttl"]) is True
    assert ontology_matches_seed(path, "acme.foo", ["ACME.foo:review.ttl"]) is True
    # The module comes from the id, not from the caller's module name.
    assert ontology_matches_seed(path, "evil", ["evil:Review.ttl"]) is False
    assert ontology_matches_seed(path, "evil", ["acme.foo:Review.ttl"]) is True


def test_an_in_engine_ontology_still_matches_by_file_name_and_path_suffix() -> None:
    path = "/app/naas_abi/ontologies/modules/FooOntology.ttl"
    assert ontology_matches_seed(path, "naas_abi", ["FooOntology.ttl"]) is True
    assert ontology_matches_seed(path, "naas_abi", ["modules/FooOntology.ttl"]) is True

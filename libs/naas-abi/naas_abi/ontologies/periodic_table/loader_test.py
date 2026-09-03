"""Tests for the ABI Periodic Table of Software ontology."""

from __future__ import annotations

from naas_abi.ontologies.periodic_table.loader import (
    GRAPH_IRI,
    MODULES_PATH,
    extract_elements,
    keep_catalog_ontology_paths,
    load_periodic_table_graph,
)


def test_canonical_modules_ontology_exists() -> None:
    assert MODULES_PATH.is_file()


def test_loads_all_119_elements() -> None:
    elements = extract_elements()
    assert len(elements) == 119
    assert elements[0].number == 1
    assert elements[0].label == "Company"
    assert elements[-1].number == 119
    assert elements[-1].local_name == "Portal"


def test_graph_parses_without_errors() -> None:
    g = load_periodic_table_graph()
    assert len(g) > 500


def test_collaboration_interfaces_present() -> None:
    elements = extract_elements()
    names = {e.local_name for e in elements}
    assert {"DocInterface", "SheetInterface", "SlideInterface", "Portal"}.issubset(names)


def test_bfo_bucket_on_every_element() -> None:
    elements = extract_elements()
    assert all(e.bfo_bucket for e in elements)
    assert all(e.bfo_abi_class.startswith("http://ontology.naas.ai/abi/") for e in elements)
    assert all("BFO_000" in e.bfo_code for e in elements)
    assert all(e.bfo_bucket_label for e in elements)


def test_named_graph_iri_is_abi_owned() -> None:
    assert GRAPH_IRI == "http://ontology.naas.ai/graph/abi-periodic-table"


def test_keep_catalog_ontology_paths_drops_authoring_fragments() -> None:
    kept = keep_catalog_ontology_paths(
        [
            "/tmp/naas_abi/ontologies/modules/PeriodicTableOntology.ttl",
            "/tmp/naas_abi/ontologies/periodic_table/schema.ttl",
            "/tmp/naas_abi/ontologies/periodic_table/elements/061_Creating.ttl",
            "/tmp/naas_abi/ontologies/modules/ABIOntology.ttl",
        ]
    )
    assert kept == [
        "/tmp/naas_abi/ontologies/modules/PeriodicTableOntology.ttl",
        "/tmp/naas_abi/ontologies/modules/ABIOntology.ttl",
    ]

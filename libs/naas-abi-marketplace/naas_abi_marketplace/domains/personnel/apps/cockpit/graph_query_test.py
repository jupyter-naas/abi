"""Tests for running the graph page's queries on a graph, whole or for one person."""

from __future__ import annotations

import pytest
from naas_abi_marketplace.domains.personnel.apps.cockpit.graph_query import (
    GRAPH_PAGE_QUERIES,
    graph_page_payload,
    query_source_rows,
)
from naas_abi_marketplace.domains.personnel.paths import DEMO_GRAPH_FILE
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

PROFILE_SLUG = URIRef("http://ontology.naas.ai/personnel/profile_slug")


@pytest.fixture(scope="module")
def demo() -> Graph:
    return Graph().parse(DEMO_GRAPH_FILE, format="turtle")


def person(graph: Graph, slug: str) -> URIRef:
    return next(graph.subjects(PROFILE_SLUG, Literal(slug, datatype=XSD.string)))


def relation_key(relation: dict) -> tuple:
    return (relation.get("from"), relation.get("to"), relation.get("label"))


def test_only_the_named_queries_run(demo: Graph) -> None:
    rows = query_source_rows(demo, labels=("find_educations",))
    assert list(rows) == ["find_educations"]


def test_binding_a_person_keeps_only_their_rows(demo: Graph) -> None:
    rows = query_source_rows(
        demo, labels=GRAPH_PAGE_QUERIES, person=person(demo, "alice_dupont")
    )
    names = {
        row["personLabel"]
        for label in GRAPH_PAGE_QUERIES
        for row in rows[label]
        if row.get("personLabel")
    }
    assert names == {"Alice Dupont"}


def test_a_person_payload_holds_everything_the_whole_graph_links_to_them(
    demo: Graph,
) -> None:
    whole = graph_page_payload(demo, org_label="Demo")
    alice = graph_page_payload(
        demo, org_label="Demo", person=person(demo, "alice_dupont")
    )
    assert [entry["label"] for entry in alice["people"]] == ["Alice Dupont"]
    touching = {
        relation_key(relation)
        for relation in whole["relations"]
        if "Alice Dupont" in relation_key(relation)[:2]
    }
    assert touching
    assert touching <= {relation_key(relation) for relation in alice["relations"]}

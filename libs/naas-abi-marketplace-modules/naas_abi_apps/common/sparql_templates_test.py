"""Template arguments cannot change a query: escaped in a literal, checked in
an IRI or a bare token (``placeholder_contexts``, ``safe_values``)."""

from __future__ import annotations

import asyncio

import pytest
from naas_abi_apps.common.sparql_templates import (
    BARE,
    IRI,
    STRING,
    Argument,
    TemplatableQuery,
    placeholder_contexts,
    query_tools,
    safe_values,
)
from naas_abi_apps.common.testing import FakeTripleStore
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import RDFS

EX = Namespace("http://example.org/")
INJECTION = 'a")) } UNION { GRAPH ?g { ?s ?p ?o } } #'


def test_contexts_follow_where_the_placeholder_stands() -> None:
    template = """
        # a "comment with a quote
        SELECT ?s WHERE {
          ?s rdfs:label ?l .
          FILTER(CONTAINS(LCASE(STR(?l)), LCASE("{{ name }}")))
          FILTER(?s != <{{ uri }}>)
          BIND('{{ other | lower }}' AS ?o)
        } LIMIT {{ limit }}
    """
    assert placeholder_contexts(template) == {
        "name": {STRING},
        "uri": {IRI},
        "other": {STRING},
        "limit": {BARE},
    }


def test_values_are_escaped_or_refused() -> None:
    contexts = {"name": {STRING}, "uri": {IRI}, "limit": {BARE}}

    assert safe_values({"name": INJECTION}, contexts)["name"] == (
        'a\\")) } UNION { GRAPH ?g { ?s ?p ?o } } #'
    )
    assert safe_values({"name": "l'eau\\\n"}, contexts)["name"] == "l\\'eau\\\\\\n"
    assert safe_values({"uri": "http://example.org/x"}, contexts) == {
        "uri": "http://example.org/x"
    }
    for bad in ("http://x> } UNION { ?s ?p ?o", "http://x y", 'http://x"'):
        with pytest.raises(ValueError, match="IRI"):
            safe_values({"uri": bad}, contexts)
    assert safe_values({"limit": "10"}, contexts) == {"limit": "10"}
    with pytest.raises(ValueError, match="number"):
        safe_values({"limit": "10 } UNION { ?s ?p ?o }"}, contexts)


def _tool(template: str, *arguments: str):
    query = TemplatableQuery(
        name="find",
        description="d",
        template=template,
        # "." is the kind of validationPattern the modules' templates use.
        arguments=tuple(Argument(a, "", ".", None) for a in arguments),
    )
    store = FakeTripleStore()
    graph = store.dataset.graph(URIRef("http://example.org/g"))
    graph.add((EX.a, RDFS.label, Literal("Alpha")))
    graph.add((EX.b, RDFS.label, Literal('Say "hi"')))
    graph.add((EX.secret, RDFS.label, Literal("Secret")))
    return query_tools([query], store)[0]


def test_an_injection_in_a_literal_finds_nothing_instead_of_everything() -> None:
    tool = _tool(
        """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?s WHERE { ?s rdfs:label ?l .
          FILTER(CONTAINS(LCASE(STR(?l)), LCASE("{{ name }}"))) }""",
        "name",
    )

    assert asyncio.run(tool.ainvoke({"name": INJECTION})) is None
    # A quote in a real value still matches.
    assert asyncio.run(tool.ainvoke({"name": 'say "hi'})) == [{"s": str(EX.b)}]


def test_an_injection_in_an_iri_is_an_error() -> None:
    tool = _tool(
        """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?l WHERE { <{{ uri }}> rdfs:label ?l }""",
        "uri",
    )

    assert asyncio.run(tool.ainvoke({"uri": str(EX.a)})) == [{"l": "Alpha"}]
    result = asyncio.run(
        tool.ainvoke({"uri": "http://x> rdfs:label ?l } UNION { ?s ?p ?l } #"})
    )
    assert "not a valid IRI" in result[0]["error"]

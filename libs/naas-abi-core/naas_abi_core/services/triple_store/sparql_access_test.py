"""What a SPARQL request reads and an update needs, for authorization."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from naas_abi_core.services.triple_store.sparql_access import (
    DEFAULT_GRAPH,
    EVERY_GRAPH,
    Need,
    analyze,
    read_shape,
    update_needs,
)
from rdflib import URIRef

MINE, SECRET = URIRef("urn:mine"), URIRef("urn:secret")


def test_service_in_an_update_needs_every_graph_even_with_using():
    needs = update_needs(
        f"INSERT {{ GRAPH <{MINE}> {{ ?s ?p ?o }} }} USING <{MINE}> "
        f"WHERE {{ SERVICE <http://127.0.0.1:7878/query> "
        f"{{ GRAPH <{SECRET}> {{ ?s ?p ?o }} }} }}"
    )
    assert Need("Query", EVERY_GRAPH) in needs
    assert Need("Insert", MINE) in needs


def test_load_needs_every_graph_as_its_source_may_be_the_stores_own():
    needs = update_needs(f"LOAD <{SECRET}> INTO GRAPH <{MINE}>")
    assert needs == [Need("Insert", MINE), Need("Query", EVERY_GRAPH)]


@pytest.mark.parametrize(
    "update",
    [
        f"INSERT {{ GRAPH <{MINE}> {{ ?s ?p ?o }} }} WHERE {{ ?s ?p ?o }}",
        "DELETE WHERE { ?s ?p ?o }",
    ],
)
def test_a_default_graph_read_is_every_graph_on_a_union_store(update):
    assert Need("Query", DEFAULT_GRAPH) in update_needs(update)
    union = update_needs(update, union_default_graph=True)
    assert Need("Query", EVERY_GRAPH) in union
    assert Need("Query", DEFAULT_GRAPH) not in union


def test_using_bounds_what_where_reads():
    needs = update_needs(
        f"INSERT {{ GRAPH <{MINE}> {{ ?s ?p ?o }} }} USING <{MINE}> "
        f"WHERE {{ ?s ?p ?o }}",
        union_default_graph=True,
    )
    assert needs == [Need("Insert", MINE), Need("Query", MINE)]


def test_a_request_is_parsed_once_as_a_query_or_an_update():
    assert not analyze("ASK { ?s ?p ?o }").update
    assert analyze("CLEAR ALL").update
    with pytest.raises(ValueError):
        analyze("SELEKT nothing")


def test_parsing_is_safe_from_many_threads():
    # pyparsing's state is global: concurrent parses must not trip each other.
    queries = [
        f"SELECT * FROM <urn:g{i}> WHERE {{ GRAPH <urn:n{i}> {{ ?s ?p ?o }} }}"
        for i in range(200)
    ]
    with ThreadPoolExecutor(16) as pool:
        shapes = list(pool.map(read_shape, queries))
    for i, shape in enumerate(shapes):
        assert shape.from_graphs == (URIRef(f"urn:g{i}"),)
        assert shape.graphs == (URIRef(f"urn:n{i}"),)


def test_copy_and_move_replace_their_target_so_they_need_clear_graph_on_it():
    def needs(request):
        return {(need.action, str(need.graph)) for need in update_needs(request)}

    copy = needs("COPY <http://g/a> TO <http://g/b>")
    assert ("ClearGraph", "http://g/b") in copy
    assert ("Insert", "http://g/b") in copy and ("Query", "http://g/a") in copy
    move = needs("MOVE <http://g/a> TO <http://g/b>")
    assert {("ClearGraph", "http://g/b"), ("DropGraph", "http://g/a")} <= move
    # ADD only inserts: the target keeps what it holds.
    assert ("ClearGraph", "http://g/b") not in needs("ADD <http://g/a> TO <http://g/b>")


def test_an_escaped_prefixed_name_reaches_the_check_with_its_backslash():
    """The parser keeps the backslash that stores drop, so the name it finds is
    not the graph the store runs: the service refuses it as no IRI."""
    from naas_abi_core.services.triple_store.TripleStorePorts import (
        Exceptions,
        checked_iri,
    )

    needs = update_needs("PREFIX g: <http://g> DROP GRAPH g:\\/private")
    (graph,) = {str(need.graph) for need in needs}
    assert "\\" in graph
    with pytest.raises(Exceptions.InvalidRequest):
        checked_iri(graph)

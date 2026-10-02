import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.triple_store_resources import (
    SCHEMA_GRAPH,
    TripleStoreResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)
from naas_abi_core.services.triple_store.TripleStoreFactory import TripleStoreFactory
from rdflib import Graph, Literal, URIRef

GRAPHS = "http://example.org/graph/"
SUBJECT = "http://example.org/thing"
PREDICATE = "http://example.org/value"


def turtle(text: str) -> bytes:
    return f'<{SUBJECT}> <{PREDICATE}> "{text}" .\n'.encode()


def _seed(service):
    for name, value in fixtures.SEED_ITEMS.items():
        graph = Graph()
        graph.add((URIRef(SUBJECT), URIRef(PREDICATE), Literal(value.decode())))
        service.insert(graph, URIRef(GRAPHS + name))
    return service


@pytest.fixture
def service(tmp_path):
    return _seed(TripleStoreFactory.TripleStoreServiceOxigraphEmbedded(str(tmp_path / "store")))


class TestTripleStoreResourcesOnEmbeddedOxigraph(ServiceResourcesContract):
    sized = False

    @pytest.fixture
    def resources(self, service):
        return TripleStoreResources(service)

    def child(self, name: str) -> str:
        return GRAPHS + name

    def encode(self, text: str) -> bytes:
        return turtle(text)

    def assert_shown(self, shown, text):
        assert shown is not None and f'"{text}"' in shown

    def assert_downloaded(self, data, text):
        assert f'"{text}"'.encode() in data

    # Every TripleStoreService bootstraps its schema graph next to the seed.
    extra_names = frozenset({"schema"})


def run(coro):
    return asyncio.run(coro)


def test_read_counts_triples_and_previews_turtle(service):
    resources = TripleStoreResources(service)
    extra = Graph()
    for i in range(3):
        extra.add((URIRef(f"{SUBJECT}/{i}"), URIRef(PREDICATE), Literal(i)))
    service.insert(extra, URIRef(GRAPHS + "alpha"))

    detail = run(resources.read(GRAPHS + "alpha"))

    assert detail.entry.attributes["triples"] == "4"
    assert detail.entry.attributes["media_type"] == "text/turtle"
    parsed = Graph().parse(data=detail.content.text, format="turtle")
    assert len(parsed) == 4


def test_previews_are_bounded_by_triples(service):
    resources = TripleStoreResources(service, preview_triples=2)
    extra = Graph()
    for i in range(5):
        extra.add((URIRef(f"{SUBJECT}/{i}"), URIRef(PREDICATE), Literal(i)))
    service.insert(extra, URIRef(GRAPHS + "big"))

    detail = run(resources.read(GRAPHS + "big"))

    assert detail.content.truncated is True
    assert len(Graph().parse(data=detail.content.text, format="turtle")) == 2
    assert detail.entry.attributes["triples"] == "5"


def test_writing_replaces_the_whole_graph(service):
    resources = TripleStoreResources(service)

    run(resources.write(GRAPHS + "alpha", turtle("replaced")))

    shown = run(resources.read(GRAPHS + "alpha")).content.text
    assert '"replaced"' in shown and '"first value"' not in shown
    assert run(resources.stat(GRAPHS + "alpha")).attributes["triples"] == "1"


def test_download_is_the_full_graph_as_turtle(service):
    resources = TripleStoreResources(service, preview_triples=1)
    extra = Graph()
    for i in range(4):
        extra.add((URIRef(f"{SUBJECT}/{i}"), URIRef(PREDICATE), Literal(i)))
    service.insert(extra, URIRef(GRAPHS + "alpha"))

    data = run(resources.download(GRAPHS + "alpha", max_bytes=1 << 20))

    assert len(Graph().parse(data=data, format="turtle")) == 5


def test_the_schema_graph_is_read_only(service):
    resources = TripleStoreResources(service)

    schema = run(resources.stat(str(SCHEMA_GRAPH)))

    assert schema.actions == ("read", "download")
    with pytest.raises(UnsupportedOperation):
        run(resources.write(str(SCHEMA_GRAPH), turtle("x")))
    with pytest.raises(UnsupportedOperation):
        run(resources.delete(str(SCHEMA_GRAPH)))
    assert str(SCHEMA_GRAPH) in {str(g) for g in service.list_graphs()}


@pytest.mark.parametrize(
    "bad",
    ["not an iri", "relative/path", "http://x.org/a>b", 'http://x.org/"q"', "http://x.org/{a}"],
)
def test_graph_names_must_be_absolute_iris(service, bad):
    resources = TripleStoreResources(service)

    with pytest.raises(InvalidResource):
        run(resources.write(bad, turtle("x")))
    with pytest.raises(ResourceNotFound):
        run(resources.stat(bad))


def test_invalid_turtle_is_rejected_without_touching_the_graph(service):
    resources = TripleStoreResources(service)

    with pytest.raises(InvalidResource):
        run(resources.write(GRAPHS + "alpha", b"this is not turtle <"))

    assert '"first value"' in run(resources.read(GRAPHS + "alpha")).content.text


def test_stores_without_named_graphs_cannot_be_written(tmp_path):
    # The filesystem adapter itself: a TripleStoreService cannot be built on it today
    # (its schema-graph bootstrap needs named graphs the adapter refuses).
    store = TripleStoreService__SecondaryAdaptor__Filesystem(str(tmp_path / "fs"))
    resources = TripleStoreResources(store)

    assert run(resources.list()).entries == ()
    with pytest.raises(UnsupportedOperation):
        run(resources.write(GRAPHS + "new", turtle("x")))


# --- listing, search and the structured preview --------------------------------------


class CountingStore:
    """The real service, counting SPARQL queries (one per page, not per row)."""

    def __init__(self, inner, *, fail_aggregates: bool = False) -> None:
        self.inner = inner
        self.queries: list[str] = []
        self.fail_aggregates = fail_aggregates

    def query(self, sparql):
        self.queries.append(sparql)
        if self.fail_aggregates and "GROUP BY" in sparql:
            raise RuntimeError("this store cannot aggregate")
        return self.inner.query(sparql)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_listing_counts_the_page_s_triples_in_one_query(service):
    extra = Graph()
    for i in range(3):
        extra.add((URIRef(f"{SUBJECT}/{i}"), URIRef(PREDICATE), Literal(i)))
    service.insert(extra, URIRef(GRAPHS + "alpha"))
    store = CountingStore(service)

    page = run(TripleStoreResources(store).list())

    counts = {e.name: e.attributes.get("triples") for e in page.entries}
    assert counts["alpha"] == "4" and counts["beta"] == "1"
    assert len(store.queries) == 1
    assert "GROUP BY" in store.queries[0] and "VALUES" in store.queries[0]


def test_the_schema_graph_is_marked(service):
    entries = {e.name: e for e in run(TripleStoreResources(service).list()).entries}

    assert entries["schema"].attributes["role"] == "schema"
    assert "role" not in entries["alpha"].attributes


def test_listing_without_aggregates_still_lists(service):
    page = run(TripleStoreResources(CountingStore(service, fail_aggregates=True)).list())

    assert {e.name for e in page.entries} >= {"alpha", "beta", "gamma"}
    assert all("triples" not in e.attributes for e in page.entries)


def test_search_filters_graph_iris_on_the_server(service):
    resources = TripleStoreResources(service)

    page = run(resources.list(query="ALP"))

    assert resources.capabilities.search is True
    assert [e.name for e in page.entries] == ["alpha"]


def _people(service, graph: str) -> None:
    people = Graph()
    ns = "http://example.org/people/"
    foaf = "http://xmlns.com/foaf/0.1/"
    rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    for i in range(4):
        person = URIRef(f"{ns}p{i}")
        people.add((person, rdf_type, URIRef(f"{foaf}Person")))
        people.add((person, URIRef(f"{foaf}name"), Literal(f"Person {i}\nline two", lang="en")))
    people.add((URIRef(f"{ns}p0"), URIRef(f"{ns}knows"), URIRef(f"{ns}p1")))
    service.insert(people, URIRef(graph))


def test_read_carries_triples_as_ntriples_terms_with_prefixes(service):
    _people(service, GRAPHS + "people")

    detail = run(TripleStoreResources(service).read(GRAPHS + "people"))
    view = detail.view

    assert view["type"] == "triples"
    assert view["total"] == 9
    assert len(view["triples"]) == 9
    assert view["triples"] == sorted(view["triples"])
    subjects = {t[0] for t in view["triples"]}
    assert "<http://example.org/people/p0>" in subjects
    names = [t[2] for t in view["triples"] if t[1] == "<http://xmlns.com/foaf/0.1/name>"]
    assert names[0] == '"Person 0\\nline two"@en'
    assert view["prefixes"]["foaf"] == "http://xmlns.com/foaf/0.1/"
    assert view["prefixes"]["people"] == "http://example.org/people/"


def test_read_summarizes_predicates_and_classes_in_one_aggregate(service):
    _people(service, GRAPHS + "people")
    store = CountingStore(service)

    view = run(TripleStoreResources(store).read(GRAPHS + "people")).view

    assert view["predicates"][:2] == [
        ["http://www.w3.org/1999/02/22-rdf-syntax-ns#type", 4],
        ["http://xmlns.com/foaf/0.1/name", 4],
    ]
    assert view["classes"] == [["http://xmlns.com/foaf/0.1/Person", 4]]
    assert view["predicate_count"] == 3 and view["class_count"] == 1
    aggregates = [q for q in store.queries if "GROUP BY" in q]
    assert len(aggregates) == 1


def test_raw_turtle_uses_the_prefixes(service):
    _people(service, GRAPHS + "people")

    text = run(TripleStoreResources(service).read(GRAPHS + "people")).content.text

    assert "@prefix foaf: <http://xmlns.com/foaf/0.1/>" in text
    assert "foaf:Person" in text


def test_a_store_that_cannot_aggregate_still_previews(service):
    _people(service, GRAPHS + "people")

    view = run(
        TripleStoreResources(CountingStore(service, fail_aggregates=True)).read(GRAPHS + "people")
    ).view

    assert len(view["triples"]) == 9
    assert "predicates" not in view

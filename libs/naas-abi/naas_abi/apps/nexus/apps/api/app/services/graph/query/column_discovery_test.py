"""Tests for column discovery (AUDIT §7b.7.2)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.query.column_discovery import (
    _slug,
    _xsd_to_datatype,
    discover_columns,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import (
    Binding,
    IGraphQueryStore,
    ResultRow,
)
from rdflib import Dataset, Graph, Namespace, URIRef
from rdflib.query import Result

DOC = "http://ontology.naas.ai/documents#"
XSD = "http://www.w3.org/2001/XMLSchema#"


def _row(**kv) -> ResultRow:
    return {k: Binding(str(v), str(v).startswith("http")) for k, v in kv.items()}


class _RoutedStore(IGraphQueryStore):
    """Routes each discovery query to canned rows by a distinctive substring."""

    def __init__(self, dt=(), rel=(), tc=(), ont=(), in_rel=(), in_tc=()) -> None:
        self._dt, self._rel, self._tc, self._ont = dt, rel, tc, ont
        self._in_rel, self._in_tc = in_rel, in_tc

    def select(self, sparql: str) -> list[ResultRow]:
        if "DATATYPE(?o)" in sparql:
            return list(self._dt)
        if "?sc" in sparql:  # incoming relation source classes (?o a ?cls . ?s ?p ?o)
            return list(self._in_tc)
        if "isIRI(?s)" in sparql:  # incoming relations (grain in object position)
            return list(self._in_rel)
        if "?tc" in sparql:
            return list(self._tc)
        if "owl:DatatypeProperty" in sparql:
            return list(self._ont)
        if "isIRI(?o)" in sparql:
            return list(self._rel)
        return []

    def count(self, sparql: str) -> int:
        return 0

    def supports_fulltext(self) -> bool:
        return False


def test_slug_and_datatype_helpers() -> None:
    assert _slug(DOC + "extracted_text") == "extracted_text"
    assert _slug(DOC + "has_chunks", "in") == "has_chunks__in"
    assert _xsd_to_datatype(XSD + "integer") == "number"
    assert _xsd_to_datatype(XSD + "dateTime") == "date"
    assert _xsd_to_datatype(XSD + "boolean") == "boolean"
    assert _xsd_to_datatype(XSD + "string") == "string"
    assert _xsd_to_datatype(None) is None


def test_discover_merges_data_and_ontology() -> None:
    store = _RoutedStore(
        dt=[
            # functional string property, all values distinct → high-cardinality → not facetable
            _row(p=DOC + "extracted_text", subjects=4, objs=4, distinct_objs=4, dt=XSD + "string"),
            # a low-cardinality string with repeats → facetable
            _row(p=DOC + "status", subjects=10, objs=10, distinct_objs=2, dt=XSD + "string"),
        ],
        rel=[_row(p=DOC + "extracted_by", subjects=4, objs=4)],
        tc=[_row(p=DOC + "extracted_by", tc=DOC + "Extraction", subjects=4)],
        ont=[
            # declared-but-empty datatype property (no instances) → ontology-only column
            _row(prop=DOC + "annotated_label", ptype="http://www.w3.org/2002/07/owl#DatatypeProperty"),
        ],
    )
    cols = {c.id: c for c in discover_columns(store, graph_uris=["g"], class_uris=[DOC + "ExtractedItem"])}

    text = cols["extracted_text"]
    assert text.kind == "property" and text.datatype == "string" and text.is_functional
    assert text.facetable is False  # 4 distinct / 4 subjects → free-text

    assert cols["status"].facetable is True  # 2 distinct / 10 subjects → low cardinality

    rel = cols["extracted_by"]
    assert rel.kind == "relation" and rel.datatype == "iri" and rel.is_functional
    assert [t.uri for t in rel.target_classes] == [DOC + "Extraction"]

    empty = cols["annotated_label"]
    assert empty.source == "ontology" and empty.instance_count == 0


def test_discovers_incoming_relations() -> None:
    # Relations where the grain is the OBJECT (?s p ?grain) are surfaced with direction "in",
    # a "__in" slug, an arrow label, and the SUBJECT's class as the target.
    store = _RoutedStore(
        in_rel=[_row(p=DOC + "has_extracted_item", objects=4)],
        in_tc=[_row(p=DOC + "has_extracted_item", sc=DOC + "Chunk", objects=4)],
    )
    cols = {c.id: c for c in discover_columns(store, graph_uris=["g"], class_uris=[DOC + "ExtractedItem"])}
    inc = cols["has_extracted_item__in"]
    assert inc.kind == "relation" and inc.direction == "in" and inc.datatype == "iri"
    assert inc.label == "← has_extracted_item"
    assert inc.instance_count == 4
    assert [t.uri for t in inc.target_classes] == [DOC + "Chunk"]


def test_non_functional_property_detected() -> None:
    # 12 (s,o) pairs over 4 subjects ⇒ some subject has multiple values ⇒ not functional.
    store = _RoutedStore(dt=[_row(p=DOC + "tag", subjects=4, objs=12, distinct_objs=6, dt=XSD + "string")])
    col = discover_columns(store, graph_uris=["g"], class_uris=[DOC + "Item"])[0]
    assert col.is_functional is False


class _CapturingStore(_RoutedStore):
    """Records the SPARQL of the target-class queries so we can assert their graph scoping."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.seen: dict[str, str] = {}

    def select(self, sparql: str):
        if "?sc" in sparql:
            self.seen["in_tc"] = sparql
        elif "?tc" in sparql:
            self.seen["tc"] = sparql
        return super().select(sparql)


def test_outgoing_target_class_resolved_cross_graph() -> None:
    # A relation whose target lives in a SECOND graph: the target-class lookup must range over
    # type_graph_uris in its OWN graph clause, while the grain anchor stays scoped to its graph.
    store = _CapturingStore(
        rel=[_row(p=DOC + "extracted_by", subjects=2, objs=2)],
        tc=[_row(p=DOC + "extracted_by", tc=DOC + "Extraction", subjects=2, tgraph="http://g/B")],
    )
    cols = {
        c.id: c
        for c in discover_columns(
            store,
            graph_uris=["http://g/A"],
            class_uris=[DOC + "Item"],
            type_graph_uris=["http://g/A", "http://g/B"],
        )
    }
    tc_sparql = store.seen["tc"]
    # Relation (?rg) and target type (?tg) use dedicated graph variables spanning both graphs.
    assert "?tg" in tc_sparql and "?rg" in tc_sparql
    assert "http://g/B" in tc_sparql
    # The grain anchor stays scoped to the requested graph only (not widened to g/B).
    assert "VALUES ?g { <http://g/A> }" in tc_sparql
    # End-to-end: the cross-graph target class is surfaced on the relation column, tagged with
    # the graph it lives in (so the UI can scope a follow to exactly that graph).
    tcs = cols["extracted_by"].target_classes
    assert [t.uri for t in tcs] == [DOC + "Extraction"]
    assert tcs[0].graph == "http://g/B"


def test_incoming_source_class_resolved_cross_graph() -> None:
    store = _CapturingStore(
        in_rel=[_row(p=DOC + "has_item", objects=3)],
        in_tc=[_row(p=DOC + "has_item", sc=DOC + "Chunk", objects=3, sgraph="http://g/B")],
    )
    cols = {
        c.id: c
        for c in discover_columns(
            store,
            graph_uris=["http://g/A"],
            class_uris=[DOC + "Item"],
            type_graph_uris=["http://g/A", "http://g/B"],
        )
    }
    in_tc_sparql = store.seen["in_tc"]
    # Relation (?rg) and source type (?sg) span both graphs; the grain anchor stays scoped to g/A.
    assert "?sg" in in_tc_sparql and "?rg" in in_tc_sparql
    assert "http://g/B" in in_tc_sparql
    assert "VALUES ?g { <http://g/A> }" in in_tc_sparql
    in_tcs = cols["has_item__in"].target_classes
    assert [t.uri for t in in_tcs] == [DOC + "Chunk"]
    assert in_tcs[0].graph == "http://g/B"


def test_type_graphs_default_to_grain_graphs() -> None:
    # With no type_graph_uris, the type lookup is scoped to the grain graphs (no cross-graph
    # widening) — preserving the original single-graph behavior.
    store = _CapturingStore(
        rel=[_row(p=DOC + "rel", subjects=1, objs=1)],
        tc=[_row(p=DOC + "rel", tc=DOC + "Other", subjects=1)],
    )
    discover_columns(store, graph_uris=["http://g/A"], class_uris=[DOC + "Item"])
    assert "VALUES ?tg { <http://g/A> }" in store.seen["tc"]


# Execute the generated queries, not just canned rows: optional ontology fields,
# cross-graph incoming/outgoing relations, and multi-class counts must survive.
class _DiscoveryMemoryStore:
    def __init__(self) -> None:
        self.dataset = Dataset()
        self.names: set[URIRef] = set()

    def query(self, query: str) -> Result:
        return self.dataset.query(query)

    def list_graphs(self) -> list[URIRef]:
        return list(self.names)

    def insert(self, triples: Graph, graph_name: URIRef) -> None:
        self.names.add(graph_name)
        for triple in triples:
            self.dataset.graph(graph_name).add(triple)


def _real_discovery_fixture() -> tuple[_DiscoveryMemoryStore, Namespace]:
    from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef
    from rdflib.namespace import XSD as XSD_NS

    ex = Namespace("urn:discovery:")
    store = _DiscoveryMemoryStore()
    data = Graph()
    for subject, cls in [(ex.alice, ex.Person), (ex.alice, ex.Employee), (ex.bob, ex.Employee)]:
        data.add((subject, RDF.type, cls))
    for subject in [ex.alice, ex.bob]:
        data.add((subject, RDFS.label, Literal(str(subject))))
        data.add((subject, ex.age, Literal(42)))
        data.add((subject, ex.active, Literal(True)))
        data.add((subject, ex.date, Literal("2026-09-18", datatype=XSD_NS.date)))
    data.add((ex.unrelated, RDF.type, ex.Other))
    data.add((ex.unrelated, ex.notSelected, Literal("Excluded")))
    store.insert(data, URIRef("urn:data"))
    links = Graph()
    links.add((ex.alice, ex.employer, ex.company))
    links.add((ex.case, ex.adviser, ex.alice))
    store.insert(links, URIRef("urn:links"))
    types = Graph()
    types.add((ex.company, RDF.type, ex.Company))
    types.add((ex.case, RDF.type, ex.Case))
    store.insert(types, URIRef("urn:types"))
    schema = Graph()
    schema.add((ex.Person, RDFS.subClassOf, ex.Agent))
    schema.add((ex.declaredOnly, RDF.type, OWL.DatatypeProperty))
    schema.add((ex.declaredOnly, RDFS.domain, ex.Agent))
    schema.add((ex.declaredOnly, RDFS.range, XSD_NS.string))
    store.insert(schema, URIRef("http://ontology.naas.ai/graph/schema"))
    private = Graph()
    private.add((ex.alice, ex.privateField, Literal("Denied")))
    private.add((ex.secret, ex.privateRelation, ex.alice))
    store.insert(private, URIRef("urn:private"))
    return store, ex


def test_generated_discovery_preserves_all_fields_and_workspace_scope() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
        WorkspaceGraphStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (
        GraphQueryTripleStoreAdapter,
    )

    memory, ex = _real_discovery_fixture()
    allowed = frozenset(["urn:data", "urn:links", "urn:types", "http://ontology.naas.ai/graph/schema"])
    store = GraphQueryTripleStoreAdapter(WorkspaceGraphStore(memory, GraphAccessScope("ws", allowed, frozenset())))
    cols = discover_columns(store, graph_uris=["urn:data"], class_uris=[str(ex.Person), str(ex.Employee)], type_graph_uris=sorted(allowed))
    by_predicate = {(c.predicate_uri, c.direction): c for c in cols}
    assert len(cols) == 7
    assert by_predicate[str(ex.age), "out"].datatype == "number"
    assert by_predicate[str(ex.age), "out"].instance_count == 2
    assert by_predicate[str(ex.age), "out"].is_functional  # Alice has two selected types, one age.
    assert by_predicate[str(ex.active), "out"].datatype == "boolean"
    assert by_predicate[str(ex.date), "out"].datatype == "date"
    assert by_predicate[str(ex.declaredOnly), "out"].source == "ontology"
    assert by_predicate[str(ex.employer), "out"].target_classes[0].uri == str(ex.Company)
    assert by_predicate[str(ex.adviser), "in"].target_classes[0].uri == str(ex.Case)
    assert all("private" not in c.predicate_uri and c.predicate_uri != str(ex.notSelected) for c in cols)


def test_discovery_executes_on_oxigraph_with_sparse_selected_class() -> None:
    import pytest
    ox = pytest.importorskip("pyoxigraph")

    memory, ex = _real_discovery_fixture()
    database = ox.Store()
    for graph in memory.list_graphs():
        database.load(input=memory.dataset.graph(graph).serialize(format="nt"), format=ox.RdfFormat.N_TRIPLES, to_graph=ox.NamedNode(str(graph)))
    # A selected class is small relative to the graph. These unrelated values must
    # not produce columns or force joins over all instances' rdf:type bindings.
    database.bulk_extend(ox.Quad(ox.NamedNode(f"urn:noise:{i}"), ox.NamedNode(str(ex.noise)), ox.Literal(str(i)), ox.NamedNode("urn:data")) for i in range(1500))

    class OxStore(IGraphQueryStore):
        def select(self, query: str) -> list[ResultRow]:
            result = database.query(query)
            names = [v.value for v in result.variables]
            return [{name: Binding(value=row[name].value, is_uri=isinstance(row[name], ox.NamedNode)) for name in names if row[name] is not None} for row in result]

        def count(self, query: str) -> int:
            raise NotImplementedError("Discovery does not run standalone counts")

        def supports_fulltext(self) -> bool:
            return False

    cols = discover_columns(OxStore(), graph_uris=["urn:data"], class_uris=[str(ex.Person)], type_graph_uris=["urn:data", "urn:links", "urn:types"])
    assert len(cols) == 7
    assert all(c.instance_count == 1 for c in cols if c.source == "data")
    assert not any(c.predicate_uri == str(ex.noise) for c in cols)
    multi = discover_columns(OxStore(), graph_uris=["urn:data"], class_uris=[str(ex.Person), str(ex.Employee)], type_graph_uris=["urn:data", "urn:links", "urn:types"])
    age = next(c for c in multi if c.predicate_uri == str(ex.age))
    assert age.instance_count == 2 and age.is_functional

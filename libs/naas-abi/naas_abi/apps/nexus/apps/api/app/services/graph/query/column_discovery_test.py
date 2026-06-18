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
        tc=[_row(p=DOC + "extracted_by", tc=DOC + "Extraction", subjects=2)],
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
    # End-to-end: the cross-graph target class is surfaced on the relation column.
    assert [t.uri for t in cols["extracted_by"].target_classes] == [DOC + "Extraction"]


def test_incoming_source_class_resolved_cross_graph() -> None:
    store = _CapturingStore(
        in_rel=[_row(p=DOC + "has_item", objects=3)],
        in_tc=[_row(p=DOC + "has_item", sc=DOC + "Chunk", objects=3)],
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
    assert [t.uri for t in cols["has_item__in"].target_classes] == [DOC + "Chunk"]


def test_type_graphs_default_to_grain_graphs() -> None:
    # With no type_graph_uris, the type lookup is scoped to the grain graphs (no cross-graph
    # widening) — preserving the original single-graph behavior.
    store = _CapturingStore(
        rel=[_row(p=DOC + "rel", subjects=1, objs=1)],
        tc=[_row(p=DOC + "rel", tc=DOC + "Other", subjects=1)],
    )
    discover_columns(store, graph_uris=["http://g/A"], class_uris=[DOC + "Item"])
    assert "VALUES ?tg { <http://g/A> }" in store.seen["tc"]

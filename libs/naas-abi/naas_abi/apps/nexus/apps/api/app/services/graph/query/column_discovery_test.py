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

    def __init__(self, dt=(), rel=(), tc=(), ont=()) -> None:
        self._dt, self._rel, self._tc, self._ont = dt, rel, tc, ont

    def select(self, sparql: str) -> list[ResultRow]:
        if "DATATYPE(?o)" in sparql:
            return list(self._dt)
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


def test_non_functional_property_detected() -> None:
    # 12 (s,o) pairs over 4 subjects ⇒ some subject has multiple values ⇒ not functional.
    store = _RoutedStore(dt=[_row(p=DOC + "tag", subjects=4, objs=12, distinct_objs=6, dt=XSD + "string")])
    col = discover_columns(store, graph_uris=["g"], class_uris=[DOC + "Item"])[0]
    assert col.is_functional is False

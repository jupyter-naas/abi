"""Tests for google-like entity search (classes ∪ individuals)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import (
    Binding,
    IGraphQueryStore,
    ResultRow,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.search import (
    _fragment,
    search_entities,
)

DOC = "http://ontology.naas.ai/documents#"
G = "http://ontology.naas.ai/graph/data"


def _row(**kv) -> ResultRow:
    return {k: Binding(str(v), str(v).startswith("http")) for k, v in kv.items()}


class _RoutedStore(IGraphQueryStore):
    """Routes the classes/individuals query to canned rows by a distinctive substring."""

    def __init__(self, classes=(), individuals=()) -> None:
        self._classes, self._individuals = classes, individuals
        self.queries: list[str] = []

    def select(self, sparql: str) -> list[ResultRow]:
        self.queries.append(sparql)
        if "GROUP BY ?cls" in sparql:  # the classes query (with COUNT)
            return list(self._classes)
        return list(self._individuals)  # the individuals query

    def count(self, sparql: str) -> int:
        return 0

    def supports_fulltext(self) -> bool:
        return False


def test_fragment_helper() -> None:
    assert _fragment(DOC + "Extraction") == "Extraction"
    assert _fragment("http://example.org/path/Thing") == "Thing"
    assert _fragment("urn:plain") == "urn:plain"


def test_class_hit_from_fragment_match() -> None:
    # A class whose fragment "Extraction" contains query "extract" → class hit.
    store = _RoutedStore(
        classes=[_row(cls=DOC + "Extraction", g=G, cnt=7)],
    )
    hits = search_entities(store, graph_uris=[G], query="extract", limit=20)
    assert len(hits) == 1
    h = hits[0]
    assert h.kind == "class"
    assert h.uri == DOC + "Extraction"
    assert h.class_uri == DOC + "Extraction"  # class: class_uri == uri
    assert h.label == "Extraction"
    assert h.class_label == "Extraction"
    assert h.graph_uri == G
    assert h.instance_count == 7


def test_individual_hit_with_rdfs_label() -> None:
    # An individual whose rdfs:label "Invoice 2024-01" matches query "invoice".
    store = _RoutedStore(
        individuals=[
            _row(
                uri=DOC + "inv_42",
                cls=DOC + "Invoice",
                label="Invoice 2024-01",
                g=G,
            )
        ],
    )
    hits = search_entities(store, graph_uris=[G], query="invoice", limit=20)
    assert len(hits) == 1
    h = hits[0]
    assert h.kind == "individual"
    assert h.uri == DOC + "inv_42"
    assert h.class_uri == DOC + "Invoice"
    assert h.class_label == "Invoice"  # fragment of class
    assert h.label == "Invoice 2024-01"
    assert h.graph_uri == G
    assert h.instance_count == 0


def test_individual_hit_matched_by_uri_fragment_when_no_label() -> None:
    # No rdfs:label → label falls back to STR(uri); the COALESCE'd label is the URI string,
    # which contains "inv_99" so the URI-fragment match path is exercised.
    store = _RoutedStore(
        individuals=[
            _row(
                uri=DOC + "inv_99",
                cls=DOC + "Invoice",
                label=DOC + "inv_99",  # COALESCE(rdfs:label, STR(uri)) fell back to the URI
                g=G,
            )
        ],
    )
    hits = search_entities(store, graph_uris=[G], query="inv_99", limit=20)
    assert len(hits) == 1
    h = hits[0]
    assert h.kind == "individual"
    assert h.label == DOC + "inv_99"
    assert h.class_uri == DOC + "Invoice"


def test_individual_search_scans_all_string_data_properties() -> None:
    # The individuals query must match over EVERY literal-valued property (not only rdfs:label)
    # or the URI — so an individual is found by its description/title/name/etc.
    store = _RoutedStore(individuals=[_row(uri=DOC + "x", cls=DOC + "Doc", label="x", g=G)])
    search_entities(store, graph_uris=[G], query="acme", limit=20)
    ind_q = next(q for q in store.queries if "GROUP BY ?cls" not in q)
    assert "?uri ?mp ?mv" in ind_q  # scans an arbitrary property ?mp with literal value ?mv
    assert "isLiteral(?mv)" in ind_q
    assert "CONTAINS(LCASE(STR(?mv))" in ind_q  # the literal value is the match target


def test_classes_first_then_individuals_and_sorting() -> None:
    # Classes ordered by -instance_count then label; individuals by label; classes before individuals.
    store = _RoutedStore(
        classes=[
            _row(cls=DOC + "Order", g=G, cnt=2),
            _row(cls=DOC + "Offer", g=G, cnt=9),
        ],
        individuals=[
            _row(uri=DOC + "o_b", cls=DOC + "Order", label="Beta order", g=G),
            _row(uri=DOC + "o_a", cls=DOC + "Order", label="Alpha order", g=G),
        ],
    )
    hits = search_entities(store, graph_uris=[G], query="o", limit=20)
    kinds = [h.kind for h in hits]
    # all classes precede all individuals
    assert kinds == ["class", "class", "individual", "individual"]
    # classes sorted by -count: Offer(9) then Order(2)
    assert [h.uri for h in hits if h.kind == "class"] == [DOC + "Offer", DOC + "Order"]
    # individuals sorted by label: Alpha then Beta
    assert [h.label for h in hits if h.kind == "individual"] == ["Alpha order", "Beta order"]


def test_limit_caps_each_kind() -> None:
    store = _RoutedStore(
        classes=[_row(cls=DOC + f"C{i}", g=G, cnt=i) for i in range(5)],
        individuals=[_row(uri=DOC + f"i{i}", cls=DOC + "C0", label=f"item {i}", g=G) for i in range(5)],
    )
    hits = search_entities(store, graph_uris=[G], query="", limit=2)
    # 2 classes + 2 individuals (query "" trivially matches via the store fake)
    assert sum(1 for h in hits if h.kind == "class") == 2
    assert sum(1 for h in hits if h.kind == "individual") == 2

"""Tests for GraphQueryService over a fake store (AUDIT §7b.6, §7b.9)."""

from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import (
    Binding,
    IGraphQueryStore,
    ResultRow,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    ClassAnchor,
    Column,
    ListSpec,
    PropertySource,
    SortKey,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.service import (
    GraphQueryService,
    _decode_cursor,
)

DOC = "http://ontology.naas.ai/documents#"
G = "http://ontology.naas.ai/graph/ws"
LBL = "http://www.w3.org/2000/01/rdf-schema#label"


class _FakeStore(IGraphQueryStore):
    def __init__(self, rows: list[ResultRow], total: int) -> None:
        self._rows = rows
        self._total = total
        self.last_select: str | None = None

    def select(self, sparql: str) -> list[ResultRow]:
        self.last_select = sparql
        return self._rows

    def count(self, sparql: str) -> int:
        return self._total

    def supports_fulltext(self) -> bool:
        return False


def _user_rows() -> list[ResultRow]:
    return [
        {"root": Binding(DOC + "u1", True), "col_name": Binding("Alice", False)},
        {"root": Binding(DOC + "u2", True), "col_name": Binding("Bob", False)},
        {"root": Binding(DOC + "u3", True), "col_name": Binding("Carol", False)},
    ]


def _spec(sort: bool = False) -> ListSpec:
    return ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "User",)),
        columns=(Column("name", "string", PropertySource(LBL)),),
        sort=(SortKey("name", "asc"),) if sort else (),
    )


def _service(store: IGraphQueryStore, owned: set[str] = frozenset({G})) -> GraphQueryService:
    return GraphQueryService(
        store, owned_graphs=lambda _ws: set(owned), system_graphs=set(), now=lambda: "2026-06-16T00:00:00+00:00"
    )


def test_run_query_assembles_rows_page_and_count() -> None:
    store = _FakeStore(_user_rows(), total=3)
    service = _service(store)
    result = asyncio.run(service.run_query(spec=_spec(), workspace_id="ws1", limit=2))

    assert result.mode == "list"
    assert [c.id for c in result.columns] == ["name"]
    # probe fetched 3 rows for limit 2 → keep 2, has_more.
    assert len(result.rows) == 2
    assert result.rows[0]["name"].value == "Alice"
    assert result.rows[0]["name"].uri is None  # a string column, not an IRI
    assert result.page.has_more is True
    assert result.page.next_cursor is not None
    assert result.count.total == 3
    assert result.count.status == "exact"
    # No sort ⇒ keyset on ?root (not offset).
    assert result.page.offset_fallback is False
    decoded = _decode_cursor(result.page.next_cursor)
    assert decoded["k"] == "keyset" and decoded["r"] == DOC + "u2"  # cursor at the last kept row


def test_ownership_violation_raises() -> None:
    store = _FakeStore(_user_rows(), total=3)
    service = _service(store, owned=frozenset({"http://other/graph"}))  # does not own G
    with pytest.raises(GraphAccessError):
        asyncio.run(service.run_query(spec=_spec(), workspace_id="ws1", limit=2))


def test_system_graph_is_queryable_even_when_not_owned() -> None:
    # Global system graphs (schema/nexus) are readable by any workspace, even though no
    # workspace "owns" them. Here G is not owned but is declared a system graph.
    store = _FakeStore(_user_rows(), total=3)
    service = GraphQueryService(
        store,
        owned_graphs=lambda _ws: {"http://other/graph"},
        system_graphs={G},
        now=lambda: "2026-06-16T00:00:00+00:00",
    )
    result = asyncio.run(service.run_query(spec=_spec(), workspace_id="ws1", limit=2))
    assert result.count.total == 3


def test_sorted_query_uses_offset_fallback() -> None:
    # Empty functional-predicate hints ⇒ a property sort key is not keyset-eligible.
    store = _FakeStore(_user_rows(), total=3)
    service = _service(store)
    result = asyncio.run(service.run_query(spec=_spec(sort=True), workspace_id="ws1", limit=2))
    assert result.page.offset_fallback is True
    decoded = _decode_cursor(result.page.next_cursor)
    assert decoded == {"k": "offset", "o": 2}  # next page starts at offset 2


def test_node_cell_carries_uri() -> None:
    rows: list[ResultRow] = [{"root": Binding(DOC + "u1", True), "col_chat": Binding(DOC + "c1", True)}]
    store = _FakeStore(rows, total=1)
    service = _service(store)
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import Hop, NodeSource

    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "User",)),
        columns=(Column("chat", "iri", NodeSource(path=(Hop(DOC + "hasChat", "out"),), show="uri")),),
    )
    result = asyncio.run(service.run_query(spec=spec, workspace_id="ws1", limit=10))
    assert result.rows[0]["chat"].value == DOC + "c1"
    assert result.rows[0]["chat"].uri == DOC + "c1"  # IRI binding → click-through uri set

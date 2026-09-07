"""Real-engine integration test for the compiler (AUDIT §7b.5, portability review).

Proves the compiled SPARQL not only *looks* right but *runs* and returns the *correct*
rows on a real triple store. Skipped unless ``NEXUS_OXIGRAPH_URL`` points at a running
store (e.g. `abi dev up --service oxigraph -d` → `abi dev ports`):

    NEXUS_OXIGRAPH_URL=http://127.0.0.1:7942 uv run python -m pytest \
        .../graph/query/compiler_integration_test.py -o addopts="" -q -m integration
"""

from __future__ import annotations

import asyncio
import os

import pytest
import requests
from naas_abi.apps.nexus.apps.api.app.services.graph.query.compiler import (
    compile_list,
    compile_query,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    AggregateSource,
    AggregateSpec,
    ClassAnchor,
    Column,
    CompileContext,
    Dimension,
    FilterColumnTarget,
    FilterCondition,
    FilterGroup,
    FilterNot,
    FilterSourceTarget,
    Hop,
    ListSpec,
    Measure,
    NodeSource,
    Page,
    PropertySource,
    SortKey,
)

DOC = "http://ontology.naas.ai/documents#"
LBL = "http://www.w3.org/2000/01/rdf-schema#label"
TG = "http://ontology.naas.ai/graph/test_compiler"

_URL = os.environ.get("NEXUS_OXIGRAPH_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _URL, reason="set NEXUS_OXIGRAPH_URL to run"),
]

_FIXTURE = f"""
DROP SILENT GRAPH <{TG}> ;
INSERT DATA {{ GRAPH <{TG}> {{
  <{DOC}paper1> a <{DOC}PDFPaperFile> ; <{DOC}path> "/data/pubmed/PMC1.pdf" ; <{DOC}has_chunks> <{DOC}chunk1> .
  <{DOC}paper2> a <{DOC}PDFPaperFile> ; <{DOC}path> "/data/arxiv/2.pdf" ; <{DOC}has_chunks> <{DOC}chunk2> .
  <{DOC}paper3> a <{DOC}PDFPaperFile> ; <{DOC}path> "/data/pubmed/PMC3.pdf" .
  <{DOC}chunk1> a <{DOC}Chunk> ; <{DOC}chunk_of> <{DOC}paper1> ; <{DOC}has_extracted_item> <{DOC}item1>, <{DOC}item2>, <{DOC}item4> .
  <{DOC}chunk2> a <{DOC}Chunk> ; <{DOC}chunk_of> <{DOC}paper2> ; <{DOC}has_extracted_item> <{DOC}item3> .
  <{DOC}item1> a <{DOC}ExtractedItem> ; <{DOC}extracted_text> "a meditation on solitude and sport" ; <{DOC}extracted_from_chunk> <{DOC}chunk1> ; <{DOC}extracted_by> <{DOC}extr_gpt> .
  <{DOC}item2> a <{DOC}ExtractedItem> ; <{DOC}extracted_text> "solitude only" ; <{DOC}extracted_from_chunk> <{DOC}chunk1> ; <{DOC}extracted_by> <{DOC}extr_other> .
  <{DOC}item3> a <{DOC}ExtractedItem> ; <{DOC}extracted_text> "solitude and sport" ; <{DOC}extracted_from_chunk> <{DOC}chunk2> ; <{DOC}extracted_by> <{DOC}extr_other> .
  <{DOC}item4> a <{DOC}ExtractedItem> ; <{DOC}extracted_text> "sport and solitude here" ; <{DOC}extracted_from_chunk> <{DOC}chunk1> ; <{DOC}extracted_by> <{DOC}extr_other> .
  <{DOC}extr_gpt> a <{DOC}Extraction> ; <{DOC}model_name> "gpt-5-mini" ; <{DOC}pipeline_name> "causes" .
  <{DOC}extr_other> a <{DOC}Extraction> ; <{DOC}model_name> "gpt-4o" ; <{DOC}pipeline_name> "effects" .
  <{DOC}u1> a <{DOC}User> ; <{LBL}> "Alice" ; <{DOC}hasChat> <{DOC}c1>, <{DOC}c2> .
  <{DOC}u2> a <{DOC}User> ; <{LBL}> "Bob" ; <{DOC}hasChat> <{DOC}c3> .
  <{DOC}u3> a <{DOC}User> ; <{LBL}> "Carol" .
  <{DOC}c1> <{DOC}hasMessage> <{DOC}m1>, <{DOC}m2> .
  <{DOC}c2> <{DOC}hasMessage> <{DOC}m3> .
  <{DOC}c3> <{DOC}hasMessage> <{DOC}m4> .
}} }}
"""


# Cross-graph fixture: the ExtractedItem lives in a different named graph from its
# chunk_of / PDFPaperFile provenance — the exact split the phases pipeline produces
# (extractions graph vs papers graph).
TG_PAPERS = "http://ontology.naas.ai/graph/test_compiler_papers"
TG_EXTR = "http://ontology.naas.ai/graph/test_compiler_extractions"

_XGRAPH_FIXTURE = f"""
DROP SILENT GRAPH <{TG_PAPERS}> ;
DROP SILENT GRAPH <{TG_EXTR}> ;
INSERT DATA {{
  GRAPH <{TG_PAPERS}> {{
    <{DOC}xp1> a <{DOC}PDFPaperFile> ; <{DOC}path> "/data/pubmed/XG1.pdf" .
    <{DOC}xc1> a <{DOC}Chunk> ; <{DOC}chunk_of> <{DOC}xp1> .
  }}
  GRAPH <{TG_EXTR}> {{
    <{DOC}xi1> a <{DOC}ExtractedItem> ; <{DOC}extracted_text> "cross graph solitude" ; <{DOC}extracted_from_chunk> <{DOC}xc1> .
  }}
}}
"""


def _update(sparql: str) -> None:
    resp = requests.post(
        f"{_URL}/update", data=sparql.encode("utf-8"),
        headers={"Content-Type": "application/sparql-update"}, timeout=15,
    )
    resp.raise_for_status()


def _select(sparql: str) -> list[dict]:
    resp = requests.post(
        f"{_URL}/query", data={"query": sparql},
        headers={"Accept": "application/sparql-results+json"}, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


def _roots(rows: list[dict]) -> set[str]:
    return {r["root"]["value"] for r in rows}


@pytest.fixture(scope="module", autouse=True)
def _load_fixture() -> None:
    _update(_FIXTURE)


def _ctx() -> CompileContext:
    return CompileContext(
        single_valued_predicates=frozenset(
            {DOC + "extracted_text", DOC + "extracted_from_chunk", DOC + "chunk_of", DOC + "path"}
        )
    )


def test_example_a_runs_and_returns_correct_rows() -> None:
    spec = ListSpec(
        graph_uris=(TG,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(
            Column("text", "string", PropertySource(DOC + "extracted_text")),
            Column(
                "paperPath", "string",
                PropertySource(DOC + "path", path=(Hop(DOC + "extracted_from_chunk", "out"), Hop(DOC + "chunk_of", "out"))),
            ),
        ),
        filters=FilterGroup("and", (
            FilterCondition(FilterColumnTarget("text"), "contains", "solitude"),
            FilterCondition(FilterColumnTarget("text"), "contains", "sport"),
            FilterCondition(FilterColumnTarget("paperPath"), "contains", "pubmed"),
        )),
    )
    compiled = compile_list(spec, _ctx())
    rows = _select(compiled.sparql)
    # item1 + item4: both have solitude AND sport, both via chunk1 → paper1 (pubmed path).
    assert _roots(rows) == {DOC + "item1", DOC + "item4"}
    # The branched paper-path column is projected on each row (SPARQL var = ?col_<id>).
    assert compiled.var_for_column["paperPath"] == "?col_paperPath"
    assert all(r["col_paperPath"]["value"] == "/data/pubmed/PMC1.pdf" for r in rows)
    # Count agrees with the page.
    total = int(_select(compiled.count_sparql)[0]["total"]["value"])
    assert total == 2


def test_cross_graph_traversal_resolves_via_from_union() -> None:
    # The regression this change targets: with the old single ``GRAPH ?g { … }`` wrapper the
    # two-hop path (ExtractedItem → chunk_of → PDFPaperFile) crossed from the extractions graph
    # into the papers graph and bound nothing, so ``paperPath`` came back empty. ``FROM
    # <papers> FROM <extractions>`` merges them, so the path resolves.
    _update(_XGRAPH_FIXTURE)
    spec = ListSpec(
        graph_uris=(TG_PAPERS, TG_EXTR),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(
            Column("text", "string", PropertySource(DOC + "extracted_text")),
            Column(
                "paperPath", "string",
                PropertySource(DOC + "path", path=(Hop(DOC + "extracted_from_chunk", "out"), Hop(DOC + "chunk_of", "out"))),
            ),
        ),
    )
    compiled = compile_list(spec, _ctx())
    rows = _select(compiled.sparql)
    # The cross-graph item is returned AND its papers-graph path is populated (was empty pre-fix).
    assert _roots(rows) == {DOC + "xi1"}
    assert all(r["col_paperPath"]["value"] == "/data/pubmed/XG1.pdf" for r in rows)


def test_example_c_negation_runs_with_vacuous_case() -> None:
    branch = PropertySource(
        DOC + "model_name",
        path=(Hop(DOC + "has_chunks", "out"), Hop(DOC + "has_extracted_item", "out"), Hop(DOC + "extracted_by", "out")),
    )
    spec = ListSpec(
        graph_uris=(TG,),
        root=ClassAnchor((DOC + "PDFPaperFile",)),
        columns=(Column("path", "string", PropertySource(DOC + "path")),),
        filters=FilterNot(FilterCondition(FilterSourceTarget(branch), "eq", "gpt-5-mini")),
    )
    compiled = compile_list(spec, _ctx())
    rows = _select(compiled.sparql)
    # paper1 EXCLUDED (item1 is gpt-5-mini); paper2 included (only gpt-4o);
    # paper3 included vacuously (no chunks/items at all).
    assert _roots(rows) == {DOC + "paper2", DOC + "paper3"}
    total = int(_select(compiled.count_sparql)[0]["total"]["value"])
    assert total == 2


def test_example_1_multihop_measures_runs() -> None:
    spec = ListSpec(
        graph_uris=(TG,),
        root=ClassAnchor((DOC + "User",)),
        columns=(
            Column("name", "string", PropertySource(LBL)),
            Column("chats", "number", AggregateSource("count", path=(Hop(DOC + "hasChat", "out"),), of_kind="node")),
            Column(
                "messages", "number",
                AggregateSource("count", path=(Hop(DOC + "hasChat", "out"), Hop(DOC + "hasMessage", "out")), of_kind="node"),
            ),
        ),
        filters=FilterCondition(FilterColumnTarget("messages"), "gt", 0),
        sort=(SortKey("messages", "desc"),),
    )
    compiled = compile_list(spec, CompileContext(single_valued_predicates=frozenset({LBL})))
    rows = _select(compiled.sparql)
    # u3 (Carol, 0 messages) is filtered out; u1 then u2 by messages desc.
    assert [r["root"]["value"] for r in rows] == [DOC + "u1", DOC + "u2"]
    by_root = {r["root"]["value"]: (int(r["col_chats"]["value"]), int(r["col_messages"]["value"])) for r in rows}
    assert by_root[DOC + "u1"] == (2, 3)  # 2 chats, 3 messages
    assert by_root[DOC + "u2"] == (1, 1)
    total = int(_select(compiled.count_sparql)[0]["total"]["value"])
    assert total == 2


def test_example_b_pivot_runs() -> None:
    spec = AggregateSpec(
        graph_uris=(TG,),
        fact=ClassAnchor((DOC + "ExtractedItem",)),
        group_by=(
            Dimension(
                "paper", "property",
                path=(Hop(DOC + "extracted_from_chunk", "out"), Hop(DOC + "chunk_of", "out")),
                show_predicate=DOC + "path",
            ),
            Dimension("pipeline", "property", path=(Hop(DOC + "extracted_by", "out"),), show_predicate=DOC + "pipeline_name"),
        ),
        measures=(Measure("items", "count", of_kind="node"),),
        sort=(SortKey("paper", "asc"),),
    )
    compiled = compile_query(spec, CompileContext())
    rows = _select(compiled.sparql)
    tuples = {
        (r["dim_paper"]["value"], r["dim_pipeline"]["value"], int(r["m_items"]["value"]))
        for r in rows
    }
    assert tuples == {
        ("/data/pubmed/PMC1.pdf", "causes", 1),   # item1
        ("/data/pubmed/PMC1.pdf", "effects", 2),  # item2 + item4
        ("/data/arxiv/2.pdf", "effects", 1),      # item3
    }
    # COUNT(*) over the group tuples = 3 distinct (paper, pipeline) pairs.
    total = int(_select(compiled.count_sparql)[0]["total"]["value"])
    assert total == 3


def test_keyset_pagination_walks_pages() -> None:
    spec = ListSpec(
        graph_uris=(TG,),
        root=ClassAnchor((DOC + "User",)),
        columns=(Column("name", "string", PropertySource(LBL)),),
        sort=(SortKey("name", "asc"),),
    )
    ctx = CompileContext(single_valued_predicates=frozenset({LBL}))
    p1 = compile_list(spec, ctx, Page(limit=2))
    rows1 = _select(p1.sparql)
    assert [r["root"]["value"] for r in rows1] == [DOC + "u1", DOC + "u2"]  # Alice, Bob
    # Build the cursor from the last row and fetch the next page.
    last = rows1[-1]
    p2 = compile_list(spec, ctx, Page(limit=2, after=(last["col_name"]["value"], last["root"]["value"])))
    rows2 = _select(p2.sparql)
    assert [r["root"]["value"] for r in rows2] == [DOC + "u3"]  # Carol
    assert not ({r["root"]["value"] for r in rows1} & {r["root"]["value"] for r in rows2})  # no overlap


def test_collapse_count_runs() -> None:
    spec = ListSpec(
        graph_uris=(TG,),
        root=ClassAnchor((DOC + "User",)),
        columns=(
            Column("name", "string", PropertySource(LBL)),
            Column("chat_count", "number", NodeSource(path=(Hop(DOC + "hasChat", "out"),), show="uri", collapse="count")),
        ),
    )
    rows = _select(compile_list(spec, CompileContext()).sparql)
    by_root = {r["root"]["value"]: int(r["col_chat_count"]["value"]) for r in rows}
    assert by_root == {DOC + "u1": 2, DOC + "u2": 1, DOC + "u3": 0}  # Carol collapses to 0


def test_aggregate_having_filter_runs() -> None:
    spec = AggregateSpec(
        graph_uris=(TG,),
        fact=ClassAnchor((DOC + "ExtractedItem",)),
        group_by=(Dimension("pipeline", "property", path=(Hop(DOC + "extracted_by", "out"),), show_predicate=DOC + "pipeline_name"),),
        measures=(Measure("items", "count", of_kind="node"),),
        filters=FilterCondition(FilterColumnTarget("items"), "gt", 1),
    )
    rows = _select(compile_query(spec, CompileContext()).sparql)
    # causes → 1 item (item1), effects → 3 (item2,3,4). HAVING items > 1 keeps only effects.
    assert {(r["dim_pipeline"]["value"], int(r["m_items"]["value"])) for r in rows} == {("effects", 3)}


def test_graph_query_service_against_live_store() -> None:
    """The whole chain: GraphQueryService → real triplestore adapter → compiler → Oxigraph."""
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (
        GraphQueryTripleStoreAdapter,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.service import GraphQueryService
    from naas_abi_core.services.triple_store.TripleStoreFactory import TripleStoreFactory

    triple_store = TripleStoreFactory.TripleStoreServiceOxigraph(oxigraph_url=_URL)
    store = GraphQueryTripleStoreAdapter(triple_store, fts_backend="none")
    service = GraphQueryService(
        store, owned_graphs=lambda _ws: {TG}, system_graphs=set(), now=lambda: "2026-06-16T00:00:00+00:00"
    )

    spec = ListSpec(
        graph_uris=(TG,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(
            Column("text", "string", PropertySource(DOC + "extracted_text")),
            Column(
                "paperPath", "string",
                PropertySource(DOC + "path", path=(Hop(DOC + "extracted_from_chunk", "out"), Hop(DOC + "chunk_of", "out"))),
            ),
        ),
        filters=FilterGroup("and", (
            FilterCondition(FilterColumnTarget("text"), "contains", "solitude"),
            FilterCondition(FilterColumnTarget("text"), "contains", "sport"),
            FilterCondition(FilterColumnTarget("paperPath"), "contains", "pubmed"),
        )),
    )
    result = asyncio.run(service.run_query(spec=spec, workspace_id="ws1", limit=10))
    assert result.mode == "list"
    assert {row["text"].value for row in result.rows}  # cells present
    assert {row["paperPath"].value for row in result.rows} == {"/data/pubmed/PMC1.pdf"}
    assert result.count.total == 2
    assert result.count.status == "exact"
    assert result.page.has_more is False


def test_graph_query_service_rejects_unowned_graph() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (
        GraphQueryTripleStoreAdapter,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.service import GraphQueryService
    from naas_abi_core.services.triple_store.TripleStoreFactory import TripleStoreFactory

    triple_store = TripleStoreFactory.TripleStoreServiceOxigraph(oxigraph_url=_URL)
    store = GraphQueryTripleStoreAdapter(triple_store)
    service = GraphQueryService(store, owned_graphs=lambda _ws: {"http://other/graph"}, system_graphs=set())
    spec = ListSpec(
        graph_uris=(TG,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(Column("text", "string", PropertySource(DOC + "extracted_text")),),
        filters=FilterCondition(FilterColumnTarget("text"), "contains", "solitude"),
    )
    with pytest.raises(GraphAccessError):
        asyncio.run(service.run_query(spec=spec, workspace_id="ws1", limit=10))


def test_column_discovery_against_live_store() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (
        GraphQueryTripleStoreAdapter,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.query.column_discovery import (
        discover_columns,
    )
    from naas_abi_core.services.triple_store.TripleStoreFactory import TripleStoreFactory

    store = GraphQueryTripleStoreAdapter(TripleStoreFactory.TripleStoreServiceOxigraph(oxigraph_url=_URL))
    cols = {c.id: c for c in discover_columns(store, graph_uris=[TG], class_uris=[DOC + "ExtractedItem"])}

    assert cols["extracted_text"].kind == "property"
    assert cols["extracted_text"].datatype == "string"
    assert cols["extracted_text"].is_functional is True
    assert cols["extracted_text"].facetable is False  # all 4 values distinct → free-text

    by = cols["extracted_by"]
    assert by.kind == "relation" and by.datatype == "iri"
    assert [t.uri for t in by.target_classes] == [DOC + "Extraction"]
    assert cols["extracted_from_chunk"].target_classes[0].uri == DOC + "Chunk"

"""Worked-example tests for the list-mode compiler (AUDIT §7b.3 / §7b.9).

These pin the compiler against the canonical AUDIT examples — written first, TDD-style.
Example A exercises the class anchor, to-one path projection, the requiredness rule
(positive conjunctive filter on a single-valued column → required join), and value
filters. Example C exercises projection-only OPTIONAL + a `not` branch → FILTER NOT EXISTS.
"""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.compiler import (
    compile_facet,
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
G = "http://ontology.naas.ai/graph/ws"
LBL = "http://www.w3.org/2000/01/rdf-schema#label"
XSD_INT = "http://www.w3.org/2001/XMLSchema#integer"


def _norm(sparql: str) -> str:
    """Collapse all whitespace so assertions are layout-insensitive."""
    return " ".join(sparql.split())


# ── Example A — list + branch ──────────────────────────────────────────────────


def _spec_a() -> ListSpec:
    return ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(
            Column("text", "string", PropertySource(DOC + "extracted_text")),
            Column(
                "paperPath",
                "string",
                PropertySource(
                    DOC + "path",
                    path=(
                        Hop(DOC + "extracted_from_chunk", "out"),
                        Hop(DOC + "chunk_of", "out"),
                    ),
                ),
            ),
        ),
        filters=FilterGroup(
            "and",
            (
                FilterCondition(FilterColumnTarget("text"), "contains", "solitude"),
                FilterCondition(FilterColumnTarget("text"), "contains", "sport"),
                FilterCondition(FilterColumnTarget("paperPath"), "contains", "pubmed"),
            ),
        ),
    )


def _ctx_a() -> CompileContext:
    return CompileContext(
        single_valued_predicates=frozenset(
            {
                DOC + "extracted_text",
                DOC + "extracted_from_chunk",
                DOC + "chunk_of",
                DOC + "path",
            }
        ),
        page_limit=100,
    )


def test_example_a_page_query() -> None:
    compiled = compile_list(_spec_a(), _ctx_a())
    expected = f"""
    SELECT ?root ?col_text ?col_paperPath WHERE {{
      VALUES ?g {{ <{G}> }}
      GRAPH ?g {{
        VALUES ?cls {{ <{DOC}ExtractedItem> }}
        ?root a ?cls .
        ?root <{DOC}extracted_text> ?col_text .
        ?root <{DOC}extracted_from_chunk> ?paperPath_0 . ?paperPath_0 <{DOC}chunk_of> ?paperPath_1 . ?paperPath_1 <{DOC}path> ?col_paperPath .
        FILTER(CONTAINS(LCASE(STR(?col_text)), "solitude"))
        FILTER(CONTAINS(LCASE(STR(?col_text)), "sport"))
        FILTER(CONTAINS(LCASE(STR(?col_paperPath)), "pubmed"))
      }}
    }}
    ORDER BY ?root LIMIT 100
    """
    assert _norm(compiled.sparql) == _norm(expected)


def test_example_a_count_query() -> None:
    compiled = compile_list(_spec_a(), _ctx_a())
    expected = f"""
    SELECT (COUNT(DISTINCT ?root) AS ?total) WHERE {{
      VALUES ?g {{ <{G}> }}
      GRAPH ?g {{
        VALUES ?cls {{ <{DOC}ExtractedItem> }}
        ?root a ?cls .
        ?root <{DOC}extracted_text> ?col_text .
        ?root <{DOC}extracted_from_chunk> ?paperPath_0 . ?paperPath_0 <{DOC}chunk_of> ?paperPath_1 . ?paperPath_1 <{DOC}path> ?col_paperPath .
        FILTER(CONTAINS(LCASE(STR(?col_text)), "solitude"))
        FILTER(CONTAINS(LCASE(STR(?col_text)), "sport"))
        FILTER(CONTAINS(LCASE(STR(?col_paperPath)), "pubmed"))
      }}
    }}
    """
    assert _norm(compiled.count_sparql) == _norm(expected)


def test_example_a_columns_metadata() -> None:
    compiled = compile_list(_spec_a(), _ctx_a())
    assert [c.id for c in compiled.columns] == ["text", "paperPath"]
    assert all(c.role == "dimension" for c in compiled.columns)
    assert compiled.var_for_column == {"text": "?col_text", "paperPath": "?col_paperPath"}


# ── Example C — negation ────────────────────────────────────────────────────────


def _spec_c() -> ListSpec:
    branch = PropertySource(
        DOC + "model_name",
        path=(
            Hop(DOC + "has_chunks", "out"),
            Hop(DOC + "has_extracted_item", "out"),
            Hop(DOC + "extracted_by", "out"),
        ),
    )
    return ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "PDFPaperFile",)),
        columns=(Column("path", "string", PropertySource(DOC + "path")),),
        filters=FilterNot(
            FilterCondition(FilterSourceTarget(branch), "eq", "gpt-5-mini")
        ),
    )


def test_example_c_page_query() -> None:
    compiled = compile_list(_spec_c(), CompileContext())
    expected = f"""
    SELECT ?root ?col_path WHERE {{
      VALUES ?g {{ <{G}> }}
      GRAPH ?g {{
        VALUES ?cls {{ <{DOC}PDFPaperFile> }}
        ?root a ?cls .
        OPTIONAL {{ ?root <{DOC}path> ?col_path . }}
        FILTER NOT EXISTS {{
          ?root <{DOC}has_chunks> ?b0_0 . ?b0_0 <{DOC}has_extracted_item> ?b0_1 . ?b0_1 <{DOC}extracted_by> ?b0_2 . ?b0_2 <{DOC}model_name> "gpt-5-mini" .
        }}
      }}
    }}
    ORDER BY ?root LIMIT 100
    """
    assert _norm(compiled.sparql) == _norm(expected)


def test_example_c_count_drops_projection_only_binding() -> None:
    compiled = compile_list(_spec_c(), CompileContext())
    expected = f"""
    SELECT (COUNT(DISTINCT ?root) AS ?total) WHERE {{
      VALUES ?g {{ <{G}> }}
      GRAPH ?g {{
        VALUES ?cls {{ <{DOC}PDFPaperFile> }}
        ?root a ?cls .
        FILTER NOT EXISTS {{
          ?root <{DOC}has_chunks> ?b0_0 . ?b0_0 <{DOC}has_extracted_item> ?b0_1 . ?b0_1 <{DOC}extracted_by> ?b0_2 . ?b0_2 <{DOC}model_name> "gpt-5-mini" .
        }}
      }}
    }}
    """
    assert _norm(compiled.count_sparql) == _norm(expected)


# ── Behaviour ───────────────────────────────────────────────────────────────────


def test_sort_descending_emits_order_by() -> None:
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(Column("text", "string", PropertySource(DOC + "extracted_text")),),
        sort=(SortKey("text", "desc"),),
    )
    compiled = compile_list(spec, CompileContext())
    assert "ORDER BY DESC(?col_text) ?root" in _norm(compiled.sparql)


def test_unknown_filter_column_is_rejected() -> None:
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(Column("text", "string", PropertySource(DOC + "extracted_text")),),
        filters=FilterCondition(FilterColumnTarget("nope"), "eq", "x"),
    )
    with pytest.raises(GraphQuerySpecError):
        compile_list(spec, CompileContext())


def test_node_column_in_filter_constrains_reached_node() -> None:
    # Filtering a related-entity (node) column by value must constrain the reached node's
    # display value — NOT merely check the relation exists (which would match every row).
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(Column("by", "iri", NodeSource((Hop(DOC + "extracted_by", "out"),), show="label")),),
        filters=FilterCondition(FilterColumnTarget("by"), "in", (DOC + "extr_other",)),
    )
    q = _norm(compile_list(spec, CompileContext()).sparql)
    assert "FILTER EXISTS {" in q
    assert "BIND(COALESCE(" in q  # the reached node's display value is computed…
    assert "IN (" in q and "extr_other" in q  # …and constrained, not dropped


def test_to_many_column_without_collapse_is_auto_collapsed() -> None:
    # A multi-hop dimension whose path isn't provably single-valued must collapse to one cell
    # per root (default concat) — a plain OPTIONAL join would multiply rows per related value.
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "Extraction",)),
        columns=(
            Column(
                "paths",
                "string",
                PropertySource(
                    DOC + "path",
                    path=(
                        Hop(DOC + "extracted_by", "in"),
                        Hop(DOC + "has_extracted_item", "in"),
                        Hop(DOC + "has_chunks", "in"),
                    ),
                ),
            ),
        ),
    )
    q = _norm(compile_list(spec, CompileContext()).sparql)
    assert "GROUP_CONCAT" in q  # collapsed to one cell…
    assert "GROUP BY ?root" in q  # …via a per-root sub-aggregate


def test_aggregate_mode_requires_dimensions_and_measures() -> None:
    spec = AggregateSpec(graph_uris=(G,), fact=ClassAnchor((DOC + "ExtractedItem",)), group_by=(), measures=())
    with pytest.raises(GraphQuerySpecError):
        compile_query(spec, CompileContext())


# ── Example 1 — list mode with multihop measures (AUDIT §7a example 1) ──────────


def _spec_1() -> ListSpec:
    return ListSpec(
        graph_uris=(G,),
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


def test_example_1_measures_page() -> None:
    compiled = compile_list(_spec_1(), CompileContext(single_valued_predicates=frozenset({LBL})))
    expected = f"""
    SELECT ?root ?col_name ?col_chats ?col_messages WHERE {{
      VALUES ?g {{ <{G}> }}
      GRAPH ?g {{
        VALUES ?cls {{ <{DOC}User> }}
        ?root a ?cls .
        OPTIONAL {{ ?root <{LBL}> ?col_name . }}
        OPTIONAL {{ SELECT ?root (COUNT(DISTINCT ?chats_0) AS ?raw_chats) WHERE {{ VALUES ?g {{ <{G}> }} GRAPH ?g {{ ?root <{DOC}hasChat> ?chats_0 . }} }} GROUP BY ?root }}
        BIND(COALESCE(?raw_chats, 0) AS ?col_chats)
        OPTIONAL {{ SELECT ?root (COUNT(DISTINCT ?messages_1) AS ?raw_messages) WHERE {{ VALUES ?g {{ <{G}> }} GRAPH ?g {{ ?root <{DOC}hasChat> ?messages_0 . ?messages_0 <{DOC}hasMessage> ?messages_1 . }} }} GROUP BY ?root }}
        BIND(COALESCE(?raw_messages, 0) AS ?col_messages)
        FILTER(?col_messages > "0"^^<{XSD_INT}>)
      }}
    }}
    ORDER BY DESC(?col_messages) ?root LIMIT 100
    """
    assert _norm(compiled.sparql) == _norm(expected)


def test_example_1_count_keeps_only_filtered_measure() -> None:
    compiled = compile_list(_spec_1(), CompileContext(single_valued_predicates=frozenset({LBL})))
    expected = f"""
    SELECT (COUNT(DISTINCT ?root) AS ?total) WHERE {{
      VALUES ?g {{ <{G}> }}
      GRAPH ?g {{
        VALUES ?cls {{ <{DOC}User> }}
        ?root a ?cls .
        OPTIONAL {{ SELECT ?root (COUNT(DISTINCT ?messages_1) AS ?raw_messages) WHERE {{ VALUES ?g {{ <{G}> }} GRAPH ?g {{ ?root <{DOC}hasChat> ?messages_0 . ?messages_0 <{DOC}hasMessage> ?messages_1 . }} }} GROUP BY ?root }}
        BIND(COALESCE(?raw_messages, 0) AS ?col_messages)
        FILTER(?col_messages > "0"^^<{XSD_INT}>)
      }}
    }}
    """
    assert _norm(compiled.count_sparql) == _norm(expected)
    # name + chats (projection-only) are dropped from the count; messages is kept.
    assert "?col_name" not in compiled.count_sparql
    assert "?raw_chats" not in compiled.count_sparql


# ── Example B — aggregate / pivot mode (AUDIT §7a example B) ─────────────────────


def _spec_b() -> AggregateSpec:
    return AggregateSpec(
        graph_uris=(G,),
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


def test_example_b_aggregate_page() -> None:
    compiled = compile_query(_spec_b(), CompileContext())
    expected = f"""
    SELECT ?dim_paper ?dim_pipeline (COUNT(DISTINCT ?fact) AS ?m_items) WHERE {{
      VALUES ?g {{ <{G}> }}
      GRAPH ?g {{
        VALUES ?cls {{ <{DOC}ExtractedItem> }}
        ?fact a ?cls .
        OPTIONAL {{ ?fact <{DOC}extracted_from_chunk> ?paper_0 . ?paper_0 <{DOC}chunk_of> ?paper_1 . ?paper_1 <{DOC}path> ?dim_paper . }}
        OPTIONAL {{ ?fact <{DOC}extracted_by> ?pipeline_0 . ?pipeline_0 <{DOC}pipeline_name> ?dim_pipeline . }}
      }}
    }}
    GROUP BY ?dim_paper ?dim_pipeline ORDER BY ASC(?dim_paper) ?dim_pipeline LIMIT 100
    """
    assert _norm(compiled.sparql) == _norm(expected)
    assert [c.id for c in compiled.columns] == ["paper", "pipeline", "items"]
    assert [c.role for c in compiled.columns] == ["dimension", "dimension", "measure"]


def test_example_b_count_is_count_of_group_tuples() -> None:
    compiled = compile_query(_spec_b(), CompileContext())
    expected = f"""
    SELECT (COUNT(*) AS ?total) WHERE {{ SELECT ?dim_paper ?dim_pipeline WHERE {{
      VALUES ?g {{ <{G}> }} GRAPH ?g {{
        VALUES ?cls {{ <{DOC}ExtractedItem> }} ?fact a ?cls .
        OPTIONAL {{ ?fact <{DOC}extracted_from_chunk> ?paper_0 . ?paper_0 <{DOC}chunk_of> ?paper_1 . ?paper_1 <{DOC}path> ?dim_paper . }}
        OPTIONAL {{ ?fact <{DOC}extracted_by> ?pipeline_0 . ?pipeline_0 <{DOC}pipeline_name> ?dim_pipeline . }}
      }} }} GROUP BY ?dim_paper ?dim_pipeline }}
    """
    assert _norm(compiled.count_sparql) == _norm(expected)


def test_aggregate_filter_dimension_where_measure_having() -> None:
    spec = AggregateSpec(
        graph_uris=(G,),
        fact=ClassAnchor((DOC + "ExtractedItem",)),
        group_by=(
            Dimension("paper", "property", path=(Hop(DOC + "extracted_from_chunk", "out"), Hop(DOC + "chunk_of", "out")), show_predicate=DOC + "path"),
        ),
        measures=(Measure("items", "count", of_kind="node"),),
        filters=FilterGroup("and", (
            FilterCondition(FilterColumnTarget("paper"), "contains", "pubmed"),
            FilterCondition(FilterColumnTarget("items"), "gt", 5),
        )),
    )
    sparql = compile_query(spec, CompileContext()).sparql
    assert 'FILTER(CONTAINS(LCASE(STR(?dim_paper)), "pubmed"))' in _norm(sparql)  # dimension → WHERE
    assert f'HAVING(COUNT(DISTINCT ?fact) > "5"^^<{XSD_INT}>)' in _norm(sparql)  # measure → HAVING


def test_aggregate_filter_complex_or_is_rejected() -> None:
    spec = AggregateSpec(
        graph_uris=(G,),
        fact=ClassAnchor((DOC + "ExtractedItem",)),
        group_by=(Dimension("pipeline", "property", path=(Hop(DOC + "extracted_by", "out"),), show_predicate=DOC + "pipeline_name"),),
        measures=(Measure("items", "count", of_kind="node"),),
        filters=FilterGroup("or", (
            FilterCondition(FilterColumnTarget("items"), "gt", 5),
            FilterCondition(FilterColumnTarget("pipeline"), "eq", "causes"),
        )),
    )
    with pytest.raises(GraphQuerySpecError):
        compile_query(spec, CompileContext())


# ── To-many collapse ────────────────────────────────────────────────────────────


def test_collapse_to_many_concat_uses_group_concat_subquery() -> None:
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "User",)),
        columns=(
            Column("chat_titles", "string", NodeSource(path=(Hop(DOC + "hasChat", "out"),), show="label", collapse="concat")),
        ),
    )
    sparql = _norm(compile_list(spec, CompileContext()).sparql)
    assert 'GROUP_CONCAT(DISTINCT STR(?chat_titles_v); SEPARATOR=", ") AS ?col_chat_titles' in sparql
    assert "GROUP BY ?root }" in sparql  # the collapse is a per-root subquery, not an inline join


def test_collapse_count_filter_is_having() -> None:
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "User",)),
        columns=(Column("chat_count", "number", NodeSource(path=(Hop(DOC + "hasChat", "out"),), show="uri", collapse="count")),),
        filters=FilterCondition(FilterColumnTarget("chat_count"), "gt", 1),
    )
    sparql = _norm(compile_list(spec, CompileContext()).sparql)
    assert f'FILTER(?col_chat_count > "1"^^<{XSD_INT}>)' in sparql  # collapsed column filters as HAVING-equiv


# ── Keyset pagination ────────────────────────────────────────────────────────────


def _name_sorted_spec() -> ListSpec:
    return ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "User",)),
        columns=(Column("name", "string", PropertySource(LBL)),),
        sort=(SortKey("name", "asc"),),
    )


def test_keyset_first_page_forces_required_sort_column() -> None:
    compiled = compile_list(_name_sorted_spec(), CompileContext(single_valued_predicates=frozenset({LBL})))
    sparql = _norm(compiled.sparql)
    assert compiled.uses_offset_fallback is False
    assert compiled.order_columns == ("name",)
    # The keyset sort column is a REQUIRED join (not OPTIONAL) so the cursor compare is non-null.
    assert f"?root <{LBL}> ?col_name ." in sparql
    assert "OPTIONAL { ?root" not in sparql
    assert sparql.endswith("ORDER BY ASC(?col_name) ?root LIMIT 100")


def test_keyset_next_page_emits_after_filter() -> None:
    page = Page(limit=2, after=("Bob", DOC + "u2"))
    compiled = compile_list(_name_sorted_spec(), CompileContext(single_valued_predicates=frozenset({LBL})), page)
    sparql = _norm(compiled.sparql)
    assert f'FILTER( ?col_name > "Bob" || (?col_name = "Bob" && STR(?root) > "{DOC}u2") )' in sparql
    assert sparql.endswith("LIMIT 2")


def test_compile_facet_strips_target_filter_keeps_others() -> None:
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "ExtractedItem",)),
        columns=(
            Column("by", "iri", NodeSource(path=(Hop(DOC + "extracted_by", "out"),), show="uri")),
            Column("text", "string", PropertySource(DOC + "extracted_text")),
        ),
        filters=FilterGroup("and", (
            FilterCondition(FilterColumnTarget("by"), "is", DOC + "extr_gpt"),  # stripped when faceting 'by'
            FilterCondition(FilterColumnTarget("text"), "contains", "sport"),   # survives
        )),
    )
    sparql = _norm(compile_facet(spec, CompileContext(), target_column_id="by"))
    assert "(COUNT(DISTINCT ?root) AS ?cnt)" in sparql
    assert "GROUP BY ?v ORDER BY DESC(?cnt) ?v LIMIT 51" in sparql
    assert "extr_gpt" not in sparql  # the target column's own filter was removed
    assert '"sport"' in sparql       # the other column's filter survives


def test_compile_facet_refuses_measure() -> None:
    spec = ListSpec(
        graph_uris=(G,),
        root=ClassAnchor((DOC + "User",)),
        columns=(Column("chats", "number", AggregateSource("count", path=(Hop(DOC + "hasChat", "out"),), of_kind="node")),),
    )
    with pytest.raises(GraphQuerySpecError):
        compile_facet(spec, CompileContext(), target_column_id="chats")


def test_measure_sort_falls_back_to_offset() -> None:
    compiled = compile_list(_spec_1(), CompileContext(single_valued_predicates=frozenset({LBL})))
    assert compiled.uses_offset_fallback is True  # sort key is a measure → not keyset-eligible
    page2 = compile_list(_spec_1(), CompileContext(single_valued_predicates=frozenset({LBL})), Page(limit=50, offset=50))
    assert _norm(page2.sparql).endswith("LIMIT 50 OFFSET 50")

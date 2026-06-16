"""Tests for the POST /api/graph/query transport schemas (AUDIT §7b.1/§7b.2)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.query import query__schema as d
from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.primary.graph_query__primary_adapter__schemas import (
    GraphQueryRequest,
    GraphQueryResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.compiler import compile_query

DOC = "http://ontology.naas.ai/documents#"
G = "http://ontology.naas.ai/graph/ws"


def test_request_parses_and_lowers_example_a_to_a_compilable_spec() -> None:
    payload = {
        "workspace_id": "ws1",
        "spec": {
            "mode": "list",
            "graph_uris": [G],
            "root": {"kind": "class", "class_uris": [DOC + "ExtractedItem"]},
            "columns": [
                {"id": "text", "datatype": "string",
                 "source": {"kind": "property", "predicate": DOC + "extracted_text"}},
                {"id": "paperPath", "datatype": "string",
                 "source": {"kind": "property", "predicate": DOC + "path",
                            "path": [{"predicate": DOC + "extracted_from_chunk", "direction": "out"},
                                     {"predicate": DOC + "chunk_of", "direction": "out"}]}},
            ],
            "filters": {"op": "and", "children": [
                {"op": "cond", "target": {"kind": "column", "column_id": "text"}, "operator": "contains", "value": "solitude"},
                {"op": "cond", "target": {"kind": "column", "column_id": "paperPath"}, "operator": "contains", "value": "pubmed"},
            ]},
        },
    }
    req = GraphQueryRequest.model_validate(payload)
    spec = req.spec.to_domain()
    assert isinstance(spec, d.ListSpec)
    assert spec.root.class_uris == (DOC + "ExtractedItem",)
    # With functional-predicate hints (what /columns will supply), the to-one filter
    # compiles to the direct FILTER form.
    ctx = d.CompileContext(single_valued_predicates=frozenset({DOC + "extracted_text"}))
    compiled = compile_query(spec, ctx)
    assert "ExtractedItem" in compiled.sparql
    assert 'CONTAINS(LCASE(STR(?col_text)), "solitude")' in compiled.sparql


def test_aggregate_request_lowers_with_measure_and_having() -> None:
    payload = {
        "workspace_id": "ws1",
        "spec": {
            "mode": "aggregate",
            "graph_uris": [G],
            "fact": {"kind": "class", "class_uris": [DOC + "ExtractedItem"]},
            "group_by": [{"id": "pipeline", "show_kind": "property", "show_predicate": DOC + "pipeline_name",
                          "path": [{"predicate": DOC + "extracted_by", "direction": "out"}]}],
            "measures": [{"id": "items", "fn": "count", "of_kind": "node"}],
            "filters": {"op": "cond", "target": {"kind": "column", "column_id": "items"}, "operator": "gt", "value": 1},
        },
    }
    spec = GraphQueryRequest.model_validate(payload).spec.to_domain()
    assert isinstance(spec, d.AggregateSpec)
    sparql = compile_query(spec, d.CompileContext()).sparql
    assert "GROUP BY ?dim_pipeline" in sparql
    assert "HAVING(" in sparql


def test_in_operator_value_list_becomes_tuple() -> None:
    payload = {
        "workspace_id": "ws1",
        "spec": {
            "mode": "list", "graph_uris": [G],
            "root": {"kind": "class", "class_uris": [DOC + "Extraction"]},
            "columns": [{"id": "model", "datatype": "string", "source": {"kind": "property", "predicate": DOC + "model_name"}}],
            "filters": {"op": "cond", "target": {"kind": "column", "column_id": "model"}, "operator": "in", "value": ["gpt-5-mini", "gpt-4o"]},
        },
    }
    spec = GraphQueryRequest.model_validate(payload).spec.to_domain()
    assert isinstance(spec.filters.value, tuple) and spec.filters.value == ("gpt-5-mini", "gpt-4o")


def test_from_result_maps_domain_to_response() -> None:
    result = d.QueryResultData(
        mode="list",
        columns=(d.ColumnMeta("text", "Text", "string", "dimension"),),
        rows=({"text": d.CellData(value="hello", uri=None)},),
        page=d.PageInfoData(limit=100, has_more=False, next_cursor=None, offset_fallback=False),
        count=d.CountInfoData(total=1, computed_at="t", status="exact", cache_key="k"),
        resolved_sparql="SELECT ...",
    )
    resp = GraphQueryResponse.from_result(result)
    assert resp.mode == "list"
    assert resp.columns[0].id == "text"
    assert resp.rows[0]["text"].value == "hello"
    assert resp.count.total == 1

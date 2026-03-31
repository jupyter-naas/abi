"""Dedicated Graph Views API endpoints."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import GraphFilter, GraphView
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import BaseModel, Field
from rdflib import URIRef
from rdflib.query import ResultRow

router = APIRouter(dependencies=[Depends(get_current_user_required)])

NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")


class GraphTripleFilter(BaseModel):
    subject_uri: str | None = None
    predicate_uri: str | None = None
    object_uri: str | None = None


class GraphFilterOption(BaseModel):
    uri: str
    label: str


class GraphFilterOptionsResponse(BaseModel):
    subjects: list[GraphFilterOption]
    predicates: list[GraphFilterOption]
    objects: list[GraphFilterOption]


class GraphViewInfo(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str
    uri: str
    name: str
    label: str
    graph_names: list[str] = Field(default_factory=list)
    filters: list[GraphTripleFilter] = Field(default_factory=list)
    scope: str = "workspace"
    user_id: str | None = None
    created_at: str | None = None


class CreateGraphView(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    graph_names: list[str] = Field(default_factory=list)
    filters: list[GraphTripleFilter] = Field(default_factory=list)
    scope: str = "workspace"
    user_id: str | None = None


class UpdateGraphView(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    uri: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    graph_names: list[str] = Field(default_factory=list)
    filters: list[GraphTripleFilter] = Field(default_factory=list)
    scope: str = "workspace"
    user_id: str | None = None


class DeleteGraphView(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    uri: str | None = None


def get_triple_store_service(request: Request) -> TripleStoreService:
    store = getattr(request.app.state, "triple_store", None)
    if store is not None:
        return store
    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        store = module.engine.services.triple_store
        request.app.state.triple_store = store
        return store
    except Exception as exc:  # pragma: no cover - runtime protection
        raise HTTPException(
            status_code=500,
            detail="Triple store is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def _normalize_filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped == "unknown":
        return None
    return stripped


def _resolve_view_uri(store: TripleStoreService, view_id: str) -> URIRef | None:
    candidate = view_id.strip()
    if not candidate:
        return None
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return URIRef(candidate)
    rows = store.query(
        f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX nexus: <http://ontology.naas.ai/nexus/>
        SELECT ?uri
        WHERE {{
            GRAPH <{str(NEXUS_GRAPH_URI)}> {{
                ?uri rdf:type nexus:GraphView .
                FILTER(STR(?uri) = "{candidate}" || STRENDS(STR(?uri), "/{candidate}"))
            }}
        }}
        LIMIT 1
        """
    )
    for row in rows:
        assert isinstance(row, ResultRow)
        return URIRef(str(row.uri))
    return None


def _graph_scope_clauses(graph_name: str) -> tuple[str, str]:
    return f"GRAPH <{graph_name}> {{", "}"


def _query_views(store: TripleStoreService, workspace_id: str) -> list[GraphViewInfo]:
    sparql_query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    SELECT ?uri ?label ?created ?graph_name ?subject_uri ?predicate_uri ?object_uri
    WHERE {{
        GRAPH <{str(NEXUS_GRAPH_URI)}> {{
            ?uri rdf:type nexus:GraphView .
            OPTIONAL {{ ?uri rdfs:label ?label . }}
            OPTIONAL {{ ?uri dcterms:created ?created . }}
            OPTIONAL {{ ?uri nexus:includesKnowledgeGraph ?graph_name . }}
            OPTIONAL {{
                ?uri nexus:hasGraphFilter ?filter .
                OPTIONAL {{ ?filter nexus:subject_uri ?subject_uri . }}
                OPTIONAL {{ ?filter nexus:predicate_uri ?predicate_uri . }}
                OPTIONAL {{ ?filter nexus:object_uri ?object_uri . }}
            }}
        }}
    }}
    """
    rows = store.query(sparql_query)
    indexed: dict[str, GraphViewInfo] = {}
    for row in rows:
        assert isinstance(row, ResultRow)
        uri = str(row.uri)
        if uri not in indexed:
            label_value = str(row.label) if getattr(row, "label", None) else uri.split("/")[-1]
            indexed[uri] = GraphViewInfo(
                workspace_id=workspace_id,
                id=uri,
                uri=uri,
                name=label_value,
                label=label_value,
                graph_names=[],
                filters=[],
                created_at=str(row.created) if getattr(row, "created", None) else None,
            )
        graph_name = str(row.graph_name) if getattr(row, "graph_name", None) else None
        if graph_name and graph_name not in indexed[uri].graph_names:
            indexed[uri].graph_names.append(graph_name)
        f_subject = _normalize_filter_value(
            str(row.subject_uri) if getattr(row, "subject_uri", None) else None
        )
        f_predicate = _normalize_filter_value(
            str(row.predicate_uri) if getattr(row, "predicate_uri", None) else None
        )
        f_object = _normalize_filter_value(
            str(row.object_uri) if getattr(row, "object_uri", None) else None
        )
        if f_subject or f_predicate or f_object:
            filter_entry = GraphTripleFilter(
                subject_uri=f_subject,
                predicate_uri=f_predicate,
                object_uri=f_object,
            )
            if filter_entry not in indexed[uri].filters:
                indexed[uri].filters.append(filter_entry)
    return sorted(indexed.values(), key=lambda view: view.name.lower())


def resolve_view_context(
    store: TripleStoreService,
    workspace_id: str,
    user_id: str,
    view_id: str,
) -> tuple[list[str], list[dict[str, str | None]], GraphViewInfo]:
    _ = workspace_id
    _ = user_id
    view_uri = _resolve_view_uri(store, view_id)
    if view_uri is None:
        raise HTTPException(status_code=404, detail="View not found")
    views = _query_views(store, workspace_id)
    target = next((view for view in views if view.uri == str(view_uri) or view.id == view_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="View not found")
    return (
        target.graph_names,
        [item.model_dump() for item in target.filters],
        target,
    )


def _build_view_graph(
    name: str,
    graph_names: list[str],
    filters: list[GraphTripleFilter],
    view_uri: URIRef | None = None,
) -> GraphView:
    view = GraphView(_uri=view_uri, label=name) if view_uri is not None else GraphView(label=name)
    view.has_graph_filter = []
    for filter_item in filters:
        subject_uri = filter_item.subject_uri or "unknown"
        predicate_uri = filter_item.predicate_uri or "unknown"
        object_uri = filter_item.object_uri or "unknown"
        label = f"Subject: {subject_uri} Predicate: {predicate_uri} Object: {object_uri}"
        view.has_graph_filter.append(
            GraphFilter(
                label=label,
                subject_uri=subject_uri,
                predicate_uri=predicate_uri,
                object_uri=object_uri,
            )
        )
    view.includes_knowledge_graph = [URIRef(graph_name) for graph_name in graph_names]
    return view


def _normalize_filter_part(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "unknown":
        return None
    return normalized


def get_graph_filters(triple_store: TripleStoreService, uris: list[str]) -> list[dict]:
    if not uris:
        return []

    values = " ".join(f"<{uri}>" for uri in uris if uri and uri.strip())
    values_clause = f"VALUES ?filter_uri {{ {values} }}" if values else ""

    def _query(values_block: str = "") -> list[dict]:
        query = f"""
        PREFIX nexus: <http://ontology.naas.ai/nexus/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?filter_uri ?label ?s ?p ?o ?o_is_literal
        WHERE {{
            GRAPH <http://ontology.naas.ai/graph/nexus> {{
                {values_block}
                ?filter_uri rdf:type nexus:GraphFilter .
                OPTIONAL {{ ?filter_uri rdfs:label ?label . }}
                OPTIONAL {{ ?filter_uri nexus:subject_uri ?s . }}
                OPTIONAL {{ ?filter_uri nexus:predicate_uri ?p . }}
                OPTIONAL {{ ?filter_uri nexus:object_uri ?o . }}
                OPTIONAL {{
                    ?filter_uri nexus:object_is_literal ?o_is_literal .
                }}
            }}
        }}
        """
        rows = triple_store.query(query)

        filters: list[dict] = []
        for row in rows:
            assert isinstance(row, ResultRow)

            filter_uri = (
                str(row.filter_uri) if hasattr(row, "filter_uri") and row.filter_uri else None
            )
            label = str(row.label) if hasattr(row, "label") and row.label else None
            s = _normalize_filter_part(str(row.s) if hasattr(row, "s") and row.s else None)
            p = _normalize_filter_part(str(row.p) if hasattr(row, "p") and row.p else None)
            o = _normalize_filter_part(str(row.o) if hasattr(row, "o") and row.o else None)

            o_is_literal = False
            if hasattr(row, "o_is_literal") and row.o_is_literal:
                val = str(row.o_is_literal).lower()
                o_is_literal = val in ["true", "1"]

            if s or p or o:
                filters.append(
                    {
                        "uri": filter_uri,
                        "label": label,
                        "subject_uri": s,
                        "predicate_uri": p,
                        "object_uri": o,
                        "o_is_literal": o_is_literal,
                    }
                )
        return filters

    filters = _query(values_clause)
    if filters:
        return filters
    # Fallback for local sandbox when stored GraphFilter URIs changed across runs.
    return _query()


@router.get("/list")
async def list_views(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    user_id: str | None = Query(default=None, description="User context ID"),
    current_user: User = Depends(get_current_user_required),
) -> list[GraphViewInfo]:
    _ = user_id
    await require_workspace_access(current_user.id, workspace_id)
    store = get_triple_store_service(request)
    views = _query_views(store, workspace_id)
    return views


@router.get("/filter-options")
async def list_graph_filter_options(
    request: Request,
    workspace_id: str,
    graph_id: str | None = Query(default=None),
    graph_names: list[str] | None = Query(default=None),
    view_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_required),
) -> GraphFilterOptionsResponse:
    await require_workspace_access(current_user.id, workspace_id)
    store = get_triple_store_service(request)

    if view_id:
        graph_names_resolved, _, _ = resolve_view_context(
            store=store,
            workspace_id=workspace_id,
            user_id=current_user.id,
            view_id=view_id,
        )
        names = graph_names_resolved
    elif graph_id:
        names = [graph_id]
    else:
        names = [name for name in (graph_names or ["default"]) if name]
    if not names:
        names = ["default"]

    def _collect_options(pattern: str) -> list[GraphFilterOption]:
        values: dict[str, str] = {}
        for graph_name in names:
            graph_clause, graph_close = _graph_scope_clauses(graph_name)
            rows = store.query(
                f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?uri ?label
                WHERE {{
                    {graph_clause}
                    {pattern}
                    OPTIONAL {{ ?uri rdfs:label ?label . }}
                    {graph_close}
                }}
                LIMIT 5000
                """
            )
            for row in rows:
                assert isinstance(row, ResultRow)
                uri = str(row.uri)
                if not uri:
                    continue
                if uri not in values:
                    label = (
                        str(row.label)
                        if getattr(row, "label", None)
                        else uri.split("/")[-1].split("#")[-1]
                    )
                    values[uri] = label
        return [
            GraphFilterOption(uri=uri, label=label)
            for uri, label in sorted(values.items(), key=lambda item: item[1].lower())
        ]

    subjects = _collect_options("?uri ?p ?o . FILTER(isIRI(?uri))")
    predicates = _collect_options("?s ?uri ?o . FILTER(isIRI(?uri))")
    objects = _collect_options("?s ?p ?uri . FILTER(isIRI(?uri))")
    return GraphFilterOptionsResponse(
        subjects=subjects,
        predicates=predicates,
        objects=objects,
    )


@router.post("/")
async def create_view(
    request: Request,
    payload: CreateGraphView,
    current_user: User = Depends(get_current_user_required),
) -> GraphViewInfo:
    _ = current_user
    await require_workspace_access(current_user.id, payload.workspace_id)
    if len(payload.filters) == 0:
        raise HTTPException(status_code=400, detail="At least one filter is required")
    if len(payload.graph_names) == 0:
        raise HTTPException(status_code=400, detail="At least one graph is required")
    view = _build_view_graph(payload.name, payload.graph_names, payload.filters)
    store = get_triple_store_service(request)
    inserted_graph = view.rdf()
    store.insert(inserted_graph, graph_name=NEXUS_GRAPH_URI)
    return GraphViewInfo(
        workspace_id=payload.workspace_id,
        id=str(view._uri),
        uri=str(view._uri),
        name=payload.name,
        label=payload.name,
        graph_names=payload.graph_names,
        filters=payload.filters,
        scope=payload.scope,
        user_id=payload.user_id,
    )


@router.put("/{view_id}")
async def update_view(
    request: Request,
    view_id: str,
    payload: UpdateGraphView,
    workspace_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_required),
) -> GraphViewInfo:
    effective_workspace_id = payload.workspace_id or workspace_id
    if not effective_workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    await require_workspace_access(current_user.id, effective_workspace_id)
    if len(payload.filters) == 0:
        raise HTTPException(status_code=400, detail="At least one filter is required")
    if len(payload.graph_names) == 0:
        raise HTTPException(status_code=400, detail="At least one graph is required")
    store = get_triple_store_service(request)
    resolved = payload.uri or view_id
    view_uri = _resolve_view_uri(store, resolved)
    if view_uri is None:
        raise HTTPException(status_code=404, detail="View not found")
    from naas_abi.pipelines.RemoveIndividualPipeline import (
        RemoveIndividualPipeline,
        RemoveIndividualPipelineConfiguration,
        RemoveIndividualPipelineParameters,
    )

    pipeline = RemoveIndividualPipeline(
        configuration=RemoveIndividualPipelineConfiguration(
            triple_store=store,
        )
    )
    pipeline.run(
        parameters=RemoveIndividualPipelineParameters(
            uri=view_uri,
            graph_uri=NEXUS_GRAPH_URI,
        )
    )
    updated_view = _build_view_graph(
        payload.name, payload.graph_names, payload.filters, view_uri=view_uri
    )
    store.insert(updated_view.rdf(), graph_name=NEXUS_GRAPH_URI)
    return GraphViewInfo(
        workspace_id=effective_workspace_id,
        id=str(view_uri),
        uri=str(view_uri),
        name=payload.name,
        label=payload.name,
        graph_names=payload.graph_names,
        filters=payload.filters,
        scope=payload.scope,
        user_id=payload.user_id,
    )


@router.delete("/{view_id}")
async def delete_view(
    request: Request,
    view_id: str,
    workspace_id: str | None = Query(default=None),
    payload: DeleteGraphView | None = None,
    current_user: User = Depends(get_current_user_required),
) -> dict[str, str]:
    effective_workspace_id = workspace_id or (payload.workspace_id if payload else None)
    if not effective_workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    await require_workspace_access(current_user.id, effective_workspace_id)
    store = get_triple_store_service(request)
    resolved = payload.uri if payload and payload.uri else view_id
    view_uri = _resolve_view_uri(store, resolved)
    if view_uri is None:
        raise HTTPException(status_code=404, detail="View not found")
    from naas_abi.pipelines.RemoveIndividualPipeline import (
        RemoveIndividualPipeline,
        RemoveIndividualPipelineConfiguration,
        RemoveIndividualPipelineParameters,
    )

    pipeline = RemoveIndividualPipeline(
        configuration=RemoveIndividualPipelineConfiguration(
            triple_store=store,
        )
    )
    pipeline.run(
        parameters=RemoveIndividualPipelineParameters(
            uri=view_uri,
            graph_uri=NEXUS_GRAPH_URI,
        )
    )
    return {"status": "deleted"}


@router.get("/{view_id}/network")
async def get_view_network(
    request: Request,
    view_id: str,
    workspace_id: str,
    graph_names: list[str] | None = Query(default=None),
    filters_uris: list[str] | None = Query(default=None),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
) -> Any:
    await require_workspace_access(current_user.id, workspace_id)
    from naas_abi.apps.nexus.apps.api.app.api.endpoints import graph as graph_endpoints

    store = get_triple_store_service(request)
    resolved_graph_names, resolved_graph_filters, _ = resolve_view_context(
        store=store,
        workspace_id=workspace_id,
        user_id=current_user.id,
        view_id=view_id,
    )
    effective_graph_names = (
        [name for name in (graph_names or []) if name and name.strip()] or resolved_graph_names
    )
    effective_filters = (
        get_graph_filters(store, filters_uris or []) if filters_uris else resolved_graph_filters
    )

    return await graph_endpoints.get_network(
        request=request,
        workspace_id=workspace_id,
        graph_names=effective_graph_names,
        graph_filters=json.dumps(effective_filters),
        limit=limit,
        current_user=current_user,
    )

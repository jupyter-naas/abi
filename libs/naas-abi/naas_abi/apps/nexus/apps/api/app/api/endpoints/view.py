"""Dedicated Graph Views API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.api.endpoints.graph import GraphEdge, GraphNode
from naas_abi.ontologies.modules.NexusPlatformOntology import GraphFilter, GraphView, KnowledgeGraph
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from pydantic import BaseModel, Field
from rdflib import OWL, RDF, RDFS, URIRef
from rdflib.query import ResultRow

router = APIRouter(dependencies=[Depends(get_current_user_required)])

NEXUS_GRAPH_URI = URIRef("http://ontology.naas.ai/graph/nexus")
GRAPH_BASE_URI = "http://ontology.naas.ai/graph/"


class GraphViewInfo(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str
    uri: str
    label: str
    description: str | None = None
    graph_names: list[str] = Field(default_factory=list)
    graph_filters: list[str] = Field(default_factory=list)
    scope: str = "workspace"


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


class CreateGraphView(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    graph_names: list[str] = Field(default_factory=list)
    filters: list[GraphTripleFilter] = Field(default_factory=list)
    scope: str = "workspace"
    user_id: str | None = None


class UpdateGraphView(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str | None = None
    uri: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    graph_names: list[str] = Field(default_factory=list)
    filters: list[GraphTripleFilter] = Field(default_factory=list)
    scope: str = "workspace"
    user_id: str | None = None


class DeleteGraphView(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str | None = None
    uri: str | None = None


class ViewOverview(BaseModel):
    kpis: dict[str, Any]
    instances_by_class: list[dict[str, Any]]


class TriplePreviewRow(BaseModel):
    subject: str
    predicate: str
    object: str


class TriplePreviewResponse(BaseModel):
    count: int
    individual_count: int
    object_properties_count: int
    data_properties_count: int
    rows: list[TriplePreviewRow]


class TriplePreviewRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    graph_names: list[str] = Field(default_factory=list)
    filters: list[GraphTripleFilter] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)


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


def _normalize_filter_part(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "unknown":
        return None
    return normalized


def _resolve_graph_uri(graph_name: str) -> str:
    candidate = graph_name.strip()
    if not candidate:
        return ""
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    return f"{GRAPH_BASE_URI}{candidate}"


def _sparql_iri(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if any(char in candidate for char in ("<", ">", '"', "'", " ")):
        return None
    return f"<{candidate}>"


def _label_from_iri(iri: str) -> str:
    return iri.split("/")[-1].split("#")[-1]


def _format_typed_label(label: str, type_label: str | None) -> str:
    if type_label and type_label.strip():
        return f"{label} (type: {type_label.strip()})"
    return label


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


@router.get("/filters/options")
async def list_graph_filter_options(
    request: Request,
    workspace_id: str,
    graph_names: list[str] | None = Query(default=None),
    subject_uri: str | None = Query(default=None),
    predicate_uri: str | None = Query(default=None),
    object_uri: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_required),
) -> GraphFilterOptionsResponse:
    await require_workspace_access(current_user.id, workspace_id)
    store = get_triple_store_service(request)

    graph_uris = [_resolve_graph_uri(name) for name in (graph_names or []) if name.strip()]
    if not graph_uris:
        graph_uris = [f"{GRAPH_BASE_URI}default"]
    graph_values = " ".join(f"<{uri}>" for uri in graph_uris)

    subject_iri = _sparql_iri(subject_uri)
    predicate_iri = _sparql_iri(predicate_uri)
    object_iri = _sparql_iri(object_uri)

    subject_filter = f"FILTER(?s = {subject_iri})" if subject_iri else ""
    predicate_filter = f"FILTER(?p = {predicate_iri})" if predicate_iri else ""
    object_filter = f"FILTER(?o = {object_iri})" if object_iri else ""
    predicate_exclusion = f"FILTER(?p != <{str(RDF.type)}>)" if subject_iri else ""

    subject_rows = store.query(
        f"""
        PREFIX rdf: <{str(RDF)}>
        PREFIX rdfs: <{str(RDFS)}>
        SELECT DISTINCT ?s ?sLabel ?typeLabel
        WHERE {{
            VALUES ?g {{ {graph_values} }}
            GRAPH ?g {{
                ?s ?p ?o .
                FILTER(isIRI(?s) && isIRI(?o))
                ?s rdf:type ?sType .
                {predicate_filter}
                {object_filter}
                OPTIONAL {{ ?s rdfs:label ?sLabel . }}
                OPTIONAL {{ ?sType rdfs:label ?typeLabel . }}
            }}
        }}
        LIMIT 5000
        """
    )
    subject_options: dict[str, str] = {}
    for row in subject_rows:
        assert isinstance(row, ResultRow)
        uri = str(row.s)
        if not uri or uri in subject_options:
            continue
        label = str(getattr(row, "sLabel", "") or _label_from_iri(uri))
        type_label = str(getattr(row, "typeLabel", "") or "").strip() or None
        subject_options[uri] = _format_typed_label(label, type_label)

    predicate_rows = store.query(
        f"""
        PREFIX rdf: <{str(RDF)}>
        PREFIX rdfs: <{str(RDFS)}>
        SELECT DISTINCT ?p ?pLabel
        WHERE {{
            VALUES ?g {{ {graph_values} }}
            GRAPH ?g {{
                ?s ?p ?o .
                FILTER(isIRI(?o))
                {subject_filter}
                {object_filter}
                {predicate_exclusion}
                OPTIONAL {{ ?p rdfs:label ?pLabel . }}
            }}
        }}
        LIMIT 5000
        """
    )
    predicate_options: dict[str, str] = {}
    for row in predicate_rows:
        assert isinstance(row, ResultRow)
        uri = str(row.p)
        if not uri or uri in predicate_options:
            continue
        label = str(getattr(row, "pLabel", "") or _label_from_iri(uri))
        predicate_options[uri] = label

    object_rows = store.query(
        f"""
        PREFIX rdf: <{str(RDF)}>
        PREFIX rdfs: <{str(RDFS)}>
        SELECT DISTINCT ?o ?oLabel ?typeLabel
        WHERE {{
            VALUES ?g {{ {graph_values} }}
            GRAPH ?g {{
                ?s ?p ?o .
                FILTER(isIRI(?o))
                {subject_filter}
                {predicate_filter}
                OPTIONAL {{ ?o rdfs:label ?oLabel . }}
                OPTIONAL {{
                    ?o rdf:type ?oType .
                    OPTIONAL {{ ?oType rdfs:label ?typeLabel . }}
                }}
            }}
        }}
        LIMIT 5000
        """
    )
    object_options: dict[str, str] = {}
    for row in object_rows:
        assert isinstance(row, ResultRow)
        uri = str(row.o)
        if not uri or uri in object_options:
            continue
        label = str(getattr(row, "oLabel", "") or _label_from_iri(uri))
        type_label = str(getattr(row, "typeLabel", "") or "").strip() or None
        object_options[uri] = _format_typed_label(label, type_label)

    return GraphFilterOptionsResponse(
        subjects=[
            GraphFilterOption(uri=uri, label=label)
            for uri, label in sorted(subject_options.items(), key=lambda item: item[1].lower())
        ],
        predicates=[
            GraphFilterOption(uri=uri, label=label)
            for uri, label in sorted(predicate_options.items(), key=lambda item: item[1].lower())
        ],
        objects=[
            GraphFilterOption(uri=uri, label=label)
            for uri, label in sorted(object_options.items(), key=lambda item: item[1].lower())
        ],
    )


@router.post("/filters/preview")
async def preview_graph_filters(
    request: Request,
    payload: TriplePreviewRequest,
    current_user: User = Depends(get_current_user_required),
) -> TriplePreviewResponse:
    await require_workspace_access(current_user.id, payload.workspace_id)
    store = get_triple_store_service(request)

    graph_uris = [_resolve_graph_uri(name) for name in payload.graph_names if name.strip()]
    if not graph_uris:
        graph_uris = [f"{GRAPH_BASE_URI}default"]
    graph_values = " ".join(f"<{uri}>" for uri in graph_uris)

    normalized_filters = payload.filters or [GraphTripleFilter()]

    def _filter_conditions(filter_item: GraphTripleFilter) -> str:
        conditions = ["?s ?p ?o ."]
        subject_iri = _sparql_iri(filter_item.subject_uri)
        predicate_iri = _sparql_iri(filter_item.predicate_uri)
        object_iri = _sparql_iri(filter_item.object_uri)
        if subject_iri:
            conditions.append(f"FILTER(?s = {subject_iri})")
        if predicate_iri:
            conditions.append(f"FILTER(?p = {predicate_iri})")
        if object_iri:
            conditions.append(f"FILTER(?o = {object_iri})")
        return " ".join(conditions)

    unique_triples: set[tuple[str, str, str]] = set()
    ordered_triples: list[tuple[str, str, str, bool, bool]] = []

    try:
        for filter_item in normalized_filters:
            filter_clause = _filter_conditions(filter_item)
            triples_rows = store.query(
                f"""
                SELECT DISTINCT ?s ?p ?o (isIRI(?o) AS ?o_is_iri) (isLiteral(?o) AS ?o_is_literal)
                WHERE {{
                    VALUES ?g {{ {graph_values} }}
                    GRAPH ?g {{
                        FILTER(?o != <{str(OWL.NamedIndividual)}>)
                        {filter_clause}
                    }}
                }}
                """
            )
            for row in triples_rows:
                assert isinstance(row, ResultRow)
                triple = (str(row.s), str(row.p), str(row.o))
                if triple in unique_triples:
                    continue
                unique_triples.add(triple)
                object_is_iri = str(getattr(row, "o_is_iri", "false")).lower() == "true"
                object_is_literal = str(getattr(row, "o_is_literal", "false")).lower() == "true"
                ordered_triples.append(
                    (
                        triple[0],
                        triple[1],
                        triple[2],
                        object_is_iri,
                        object_is_literal,
                    )
                )
    except Exception:
        # Keep preview endpoint stable even if the triple-store rejects a query pattern.
        return TriplePreviewResponse(
            count=0,
            individual_count=0,
            object_properties_count=0,
            data_properties_count=0,
            rows=[],
        )

    total_count = len(unique_triples)
    object_properties_count = 0
    data_properties_count = 0
    nodes: set[str] = set()
    for subject, predicate, object_value, object_is_iri, object_is_literal in ordered_triples:
        if object_is_iri and predicate != str(RDF.type):
            object_properties_count += 1
        if object_is_literal:
            data_properties_count += 1
        if subject.startswith("http://") or subject.startswith("https://"):
            nodes.add(subject)
        if predicate == str(RDF.type):
            continue
        if object_is_iri and (
            object_value.startswith("http://") or object_value.startswith("https://")
        ):
            nodes.add(object_value)
    individual_count = len(nodes)

    rows: list[TriplePreviewRow] = []
    for subject, predicate, object_value, _, _ in ordered_triples[: int(payload.limit)]:
        s_label = (
            _label_from_iri(subject) if subject.startswith(("http://", "https://")) else subject
        )
        p_label = (
            _label_from_iri(predicate)
            if predicate.startswith(("http://", "https://"))
            else predicate
        )
        o_label = (
            _label_from_iri(object_value)
            if object_value.startswith(("http://", "https://"))
            else object_value
        )
        rows.append(
            TriplePreviewRow(
                subject=s_label,
                predicate=p_label,
                object=o_label,
            )
        )

    return TriplePreviewResponse(
        count=total_count,
        individual_count=individual_count,
        object_properties_count=object_properties_count,
        data_properties_count=data_properties_count,
        rows=rows,
    )


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

    sparql_query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    SELECT ?uri ?label ?description ?graph_names ?graph_filters
    WHERE {{
        GRAPH <{str(NEXUS_GRAPH_URI)}> {{
        ?uri rdf:type nexus:GraphView .
        ?uri rdfs:label ?label .
        OPTIONAL {{ ?uri nexus:description ?description . }}
        ?uri nexus:includesKnowledgeGraph ?graph_names .
        ?uri nexus:hasGraphFilter ?graph_filters .
        }}
    }}
    """
    rows = store.query(sparql_query)
    views_by_id: dict[str, dict] = {}
    for row in rows:
        assert isinstance(row, ResultRow)
        view_id = str(row.uri)
        graph_name = str(row.graph_names)
        graph_filter = str(row.graph_filters)

        if view_id not in views_by_id:
            views_by_id[view_id] = {
                "id": view_id.split("/")[-1],
                "uri": view_id,
                "label": str(row.label),
                "description": (
                    str(row.description) if getattr(row, "description", None) is not None else None
                ),
                "graph_names": [],
                "graph_filters": [],
                "scope": "workspace",
                "user_id": None,
                "created_at": None,
            }

        if graph_name not in views_by_id[view_id]["graph_names"]:
            views_by_id[view_id]["graph_names"].append(graph_name)
        if graph_filter not in views_by_id[view_id]["graph_filters"]:
            views_by_id[view_id]["graph_filters"].append(graph_filter)

    graph_views: list[GraphViewInfo] = []
    for view in views_by_id.values():
        graph_views.append(
            GraphViewInfo(
                workspace_id=workspace_id,
                id=view["id"],
                uri=view["uri"],
                label=view["label"],
                description=view["description"],
                graph_names=view["graph_names"],
                graph_filters=view["graph_filters"],
                scope=view["scope"],
            )
        )
    return graph_views


@router.get("/{view_id}")
async def get_view(
    request: Request,
    view_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user_required),
) -> GraphViewInfo:
    # await require_workspace_access(current_user.id, workspace_id)

    store = get_triple_store_service(request)

    view_uri = f"http://ontology.naas.ai/abi/{view_id}"

    sparql_query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX nexus: <http://ontology.naas.ai/nexus/>
    PREFIX abi: <http://ontology.naas.ai/abi/>
    SELECT ?uri ?label ?description ?graph_names ?graph_filters
    WHERE {{
        GRAPH <{str(NEXUS_GRAPH_URI)}> {{
        FILTER(STR(?uri) = "{view_uri}")
        ?uri rdfs:label ?label .
        OPTIONAL {{ ?uri nexus:description ?description . }}
        ?uri nexus:includesKnowledgeGraph ?graph_names .
        ?uri nexus:hasGraphFilter ?graph_filters .
        }}
    }}
    """
    rows = store.query(sparql_query)
    view_info: GraphViewInfo | None = None
    for row in rows:
        assert isinstance(row, ResultRow)
        row_view_uri = str(row.uri)
        graph_name = str(row.graph_names)
        graph_filter = str(row.graph_filters)

        if view_info is None:
            view_info = GraphViewInfo(
                workspace_id=workspace_id,
                id=row_view_uri.split("/")[-1],
                uri=row_view_uri,
                label=str(row.label),
                description=(
                    str(row.description) if getattr(row, "description", None) is not None else None
                ),
                graph_names=[],
                graph_filters=[],
                scope="workspace",
            )

        if graph_name not in view_info.graph_names:
            view_info.graph_names.append(graph_name)
        if graph_filter not in view_info.graph_filters:
            view_info.graph_filters.append(graph_filter)

    # To do: assert

    if view_info is None:
        raise HTTPException(status_code=404, detail="View not found")

    return view_info


@router.post("")
@router.post("/")
async def create_view(
    request: Request,
    payload: CreateGraphView,
    current_user: User = Depends(get_current_user_required),
) -> dict[str, Any]:

    from rdflib import Graph

    await require_workspace_access(current_user.id, payload.workspace_id)

    if len(payload.filters) == 0:
        raise HTTPException(status_code=400, detail="At least one filter is required")
    if len(payload.graph_names) == 0:
        raise HTTPException(status_code=400, detail="At least one graph is required")

    store = get_triple_store_service(request)

    # Create graph filters
    inserted_graph = Graph()
    graph_filters: list[GraphFilter | URIRef | str] = []
    for filter in payload.filters:
        label = f"subject:{filter.subject_uri}|predicate:{filter.predicate_uri}|object:{filter.object_uri}"
        graph_filter = GraphFilter(
            label=label,
            subject_uri=filter.subject_uri if filter.subject_uri else "unknown",
            predicate_uri=filter.predicate_uri if filter.predicate_uri else "unknown",
            object_uri=filter.object_uri if filter.object_uri else "unknown",
            creator=current_user.id,
        )
        inserted_graph += graph_filter.rdf()
        graph_filters.append(graph_filter)

    # List graphs
    graphs: list[KnowledgeGraph | URIRef | str] = [
        GRAPH_BASE_URI + graph_name for graph_name in payload.graph_names
    ]

    # Create graph view
    view = GraphView(
        label=payload.name,
        description=payload.description,
        has_graph_filter=graph_filters,
        includes_knowledge_graph=graphs,
        creator=current_user.id,
    )
    inserted_graph = view.rdf()
    store.insert(inserted_graph, graph_name=NEXUS_GRAPH_URI)
    return {
        "status": "created",
        "view_id": str(view._uri).split("/")[-1],
        "view_uri": str(view._uri),
        "view_label": view.label,
        "view_description": view.description,
        "view_has_graph_filter": view.has_graph_filter,
        "view_includes_knowledge_graph": view.includes_knowledge_graph,
        "total_triples": len(inserted_graph),
        "graph": inserted_graph.serialize(format="turtle"),
    }


@router.delete("/{view_id}")
async def delete_view(
    request: Request,
    view_id: str,
    workspace_id: str | None = Query(default=None),
    payload: DeleteGraphView | None = None,
    current_user: User = Depends(get_current_user_required),
) -> dict[str, Any]:
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
    graph = pipeline.run(
        parameters=RemoveIndividualPipelineParameters(
            uri=view_uri,
            graph_names=[NEXUS_GRAPH_URI],
        )
    )
    return {
        "status": "deleted",
        "view_id": str(view_uri).split("/")[-1],
        "view_uri": str(view_uri),
        "total_triples": len(graph),
        "graph": graph.serialize(format="turtle"),
    }


@router.get("/{view_id}/overview")
async def get_view_overview(
    request: Request,
    view_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
) -> ViewOverview:
    """Get overview of a given graph."""
    await require_workspace_access(current_user.id, workspace_id)

    view_data = await get_view_network(
        request=request,
        view_id=view_id,
        workspace_id=workspace_id,
        limit=limit,
        current_user=current_user,
    )

    nodes: list[GraphNode] = view_data.nodes
    edges: list[GraphEdge] = view_data.edges

    kpis = {
        "total_instances": len(nodes),
        "total_relationships": len(edges),
        "average_degree": (2 * len(edges) / len(nodes)) if nodes else 0,
        "density": (len(edges) / (len(nodes) * (len(nodes) - 1))) if len(nodes) > 1 else 0,
    }
    type_counts: dict[str, int] = {}
    for node in nodes:
        node_type = (node.type or "unknown").strip() or "unknown"
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    instances_by_class = [
        {"type": node_type, "count": count}
        for node_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    return ViewOverview(
        kpis=kpis,
        instances_by_class=instances_by_class,
    )


@router.get("/{view_id}/network")
async def get_view_network(
    request: Request,
    view_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
) -> Any:
    # await require_workspace_access(current_user.id, workspace_id)
    from naas_abi.apps.nexus.apps.api.app.api.endpoints import graph as graph_endpoints

    store = get_triple_store_service(request)

    view_info = await get_view(
        request=request,
        view_id=view_id,
        workspace_id=workspace_id,
        current_user=current_user,
    )
    graph_names = view_info.graph_names
    graph_filters = view_info.graph_filters

    graph_filters_resolved = get_graph_filters(store, graph_filters or [])

    return graph_endpoints.list_individuals(
        triple_store=store,
        workspace_id=workspace_id,
        graph_names=graph_names,
        graph_filters=graph_filters_resolved,
        limit=limit,
        depth=2,
    )

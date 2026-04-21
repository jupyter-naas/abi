"""Ontology FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary.ontology__primary_adapter__dependencies import (  # noqa: E501
    get_ontology_service,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary.ontology__primary_adapter__schemas import (  # noqa: E501
    EntityCreate,
    ImportRequest,
    OntologyFileItem,
    OntologyItem,
    OntologyOverviewAggregateStats,
    OntologyOverviewGraph,
    OntologyOverviewGraphEdge,
    OntologyOverviewGraphNode,
    OntologyOverviewStats,
    OntologyTypeCounts,
    ReferenceClass,
    ReferenceOntology,
    ReferenceProperty,
    RelationshipCreate,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyFileNotFoundError,
    OntologyParseError,
    OntologyPathNotFoundError,
    OntologyServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class OntologyFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


# ── Converters ────────────────────────────────────────────────────────────────


def _item_to_schema(item) -> OntologyItem:
    return OntologyItem(
        id=item.id,
        name=item.name,
        type=item.type,
        description=item.description,
        example=item.example,
        parent_id=item.parent_id,
        parent_name=item.parent_name,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _node_to_schema(node) -> OntologyOverviewGraphNode:
    return OntologyOverviewGraphNode(
        id=node.id,
        label=node.label,
        type=node.type,
        properties=node.properties,
    )


def _edge_to_schema(edge) -> OntologyOverviewGraphEdge:
    return OntologyOverviewGraphEdge(
        id=edge.id,
        source=edge.source,
        target=edge.target,
        type=edge.type,
        label=edge.label,
        properties=edge.properties,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("")
async def list_ontology_items(
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> dict:
    """List all ontology items (OWL Classes and Object Properties)."""
    try:
        items = await ontology_service.list_items()
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": [_item_to_schema(i) for i in items]}


@router.get("/classes")
async def list_classes(
    ontology_path: str | None = Query(None, alias="ontology_path"),
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> dict:
    """List ontology classes by file path (or all when omitted)."""
    try:
        items = await ontology_service.list_classes(ontology_path=ontology_path)
    except OntologyPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": [_item_to_schema(i) for i in items]}


@router.get("/relationships")
async def list_relations(
    ontology_path: str | None = Query(None, alias="ontology_path"),
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> dict:
    """List ontology object properties by file path (or all when omitted)."""
    try:
        items = await ontology_service.list_relations(ontology_path=ontology_path)
    except OntologyPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": [_item_to_schema(i) for i in items]}


@router.get("/ontologies")
async def list_ontology_files(
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> dict:
    """List ontology files from all registered modules."""
    try:
        items = await ontology_service.list_ontology_files()
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "items": [
            OntologyFileItem(
                name=i.name,
                path=i.path,
                module_name=i.module_name,
                submodule_name=i.submodule_name,
                description=i.description,
                license=i.license,
                contributors=i.contributors,
                date=i.date,
                imports=i.imports,
            )
            for i in items
        ]
    }


@router.get("/overview/stats")
async def get_ontology_overview_stats(
    ontology_path: str = Query(..., alias="ontology_path", min_length=1),
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> OntologyOverviewStats:
    """Return element counts for a specific ontology path."""
    try:
        stats = await ontology_service.get_overview_stats(ontology_path=ontology_path)
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail="Failed to compute ontology overview stats") from exc
    return OntologyOverviewStats(
        name=stats.name,
        path=stats.path,
        total_items=stats.total_items,
        classes=stats.classes,
        object_properties=stats.object_properties,
        data_properties=stats.data_properties,
        named_individuals=stats.named_individuals,
        imports=stats.imports,
    )


@router.get("/overview/stats/all")
async def get_all_ontologies_overview_stats(
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> OntologyOverviewAggregateStats:
    """Return consolidated overview stats across all registered ontology files."""
    try:
        stats = await ontology_service.get_all_overview_stats()
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail="Failed to compute consolidated ontology overview stats") from exc
    return OntologyOverviewAggregateStats(
        name=stats.name,
        path=stats.path,
        ontologies_count=stats.ontologies_count,
        total_items=stats.total_items,
        classes=stats.classes,
        object_properties=stats.object_properties,
        data_properties=stats.data_properties,
        named_individuals=stats.named_individuals,
        imports=stats.imports,
    )


@router.get("/counts/types")
async def get_ontology_type_counts(
    ontology_path: str | None = Query(None, alias="ontology_path"),
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> OntologyTypeCounts:
    """Return counts for owl:NamedIndividual and owl:DatatypeProperty."""
    try:
        counts = await ontology_service.get_type_counts(ontology_path=ontology_path)
    except OntologyPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail="Failed to compute ontology type counts") from exc
    return OntologyTypeCounts(
        name=counts.name,
        path=counts.path,
        data_properties=counts.data_properties,
        named_individuals=counts.named_individuals,
    )


@router.get("/overview/graph")
async def get_ontology_overview_graph(
    ontology_path: str | None = Query(None, alias="ontology_path"),
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> OntologyOverviewGraph:
    """Return ontology dependency graph based on owl:imports relations."""
    try:
        graph = await ontology_service.get_overview_graph(ontology_path=ontology_path)
    except OntologyPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to compute ontology overview graph",
                "mode": "single_ontology" if ontology_path else "imports_overview",
                "ontology_path": ontology_path,
                "error": str(exc),
            },
        ) from exc
    return OntologyOverviewGraph(
        nodes=[_node_to_schema(n) for n in graph.nodes],
        edges=[_edge_to_schema(e) for e in graph.edges],
    )


@router.post("/entity")
async def create_entity(
    data: EntityCreate,
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> OntologyItem:
    """Create a new ontology entity."""
    item = await ontology_service.create_entity(
        name=data.name,
        description=data.description,
        base_class=data.base_class,
    )
    return _item_to_schema(item)


@router.post("/relationship")
async def create_relationship(
    data: RelationshipCreate,
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> OntologyItem:
    """Create a new ontology relationship."""
    item = await ontology_service.create_relationship(
        name=data.name,
        description=data.description,
        base_property=data.base_property,
    )
    return _item_to_schema(item)


@router.delete("/{item_id}")
async def delete_item(
    item_id: str,
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> dict:
    """Delete an ontology item."""
    await ontology_service.delete_item(item_id=item_id)
    return {"success": True}


@router.post("/import")
async def import_reference_ontology(
    request: ImportRequest,
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> dict:
    """Import a reference ontology from content (TTL, OWL, RDF)."""
    try:
        ontology = await ontology_service.import_ontology(
            content=request.content,
            filename=request.filename,
        )
    except OntologyParseError as exc:
        raise HTTPException(status_code=500, detail="Failed to parse ontology file") from exc
    return ReferenceOntology(
        id=ontology.id,
        name=ontology.name,
        file_path=ontology.file_path,
        format=ontology.format,
        classes=[
            ReferenceClass(
                iri=c.iri,
                label=c.label,
                definition=c.definition,
                examples=c.examples,
                sub_class_of=c.sub_class_of,
            )
            for c in ontology.classes
        ],
        properties=[
            ReferenceProperty(
                iri=p.iri,
                label=p.label,
                definition=p.definition,
                inverse_of=p.inverse_of,
            )
            for p in ontology.properties
        ],
        imported_at=ontology.imported_at,
    ).model_dump()


@router.get("/export")
async def export_ontology_file(
    ontology_path: str = Query(..., alias="ontology_path", min_length=1),
    ontology_service: OntologyService = Depends(get_ontology_service),
) -> FileResponse:
    """Export a selected ontology file as attachment."""
    try:
        path = await ontology_service.export_ontology_file(ontology_path=ontology_path)
    except OntologyFileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Ontology file does not exist") from exc
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )

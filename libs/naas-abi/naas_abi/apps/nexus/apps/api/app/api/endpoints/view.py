"""Dedicated Graph Views API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.api.endpoints.graph import GraphData, GraphEdge, GraphNode
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.view.service import (
    ViewNotFoundError,
    ViewService,
    ViewServiceUnavailableError,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class GraphViewInfo(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    id: str
    uri: str
    label: str
    name: str | None = None
    description: str | None = None
    view_type: str = "Unknown"
    kind: str = "network"
    visibility: str = "workspace"
    creator_id: str | None = None
    graph_id: str | None = None
    graph_uri: str | None = None
    graph_names: list[str] = Field(default_factory=list)
    graph_filters: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    path: str = ""
    scope: str = "workspace"
    created_at: str | None = None
    updated_at: str | None = None


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
    view_type: str = Field(default="Unknown", max_length=100)
    kind: str = Field(default="network", max_length=50, pattern="^(network|filter|query)$")
    visibility: str = Field(default="workspace", max_length=20, pattern="^(workspace)$")
    graph_id: str = Field(..., min_length=1, max_length=255)
    graph_uri: str = Field(..., min_length=1)
    state: dict[str, Any] = Field(default_factory=dict)
    path: str = Field(default="", max_length=1024)
    description: str | None = None
    graph_names: list[str] = Field(default_factory=list)
    filters: list[GraphTripleFilter] = Field(default_factory=list)
    user_id: str | None = None


class UpdateGraphView(BaseModel):
    """PUT/PATCH body. All mutable fields optional → partial update. id/created_at immutable."""

    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    path: str | None = Field(default=None, max_length=1024)
    state: dict[str, Any] | None = None
    visibility: str | None = Field(default=None, pattern="^(workspace)$")
    view_type: str | None = Field(default=None, max_length=100)
    kind: str | None = Field(default=None, pattern="^(network|filter|query)$")


class FolderNode(BaseModel):
    path: str
    name: str
    view_count: int = 0
    total_count: int = 0


class FolderListResponse(BaseModel):
    folders: list[FolderNode] = Field(default_factory=list)


class RenameFolderRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    from_path: str = Field(..., max_length=1024)
    to_path: str = Field(default="", max_length=1024)
    merge: bool = False


class RenameFolderResponse(BaseModel):
    status: str = "renamed"
    from_path: str
    to_path: str
    updated_count: int


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


def _get_view_service(_request: Request, db: AsyncSession) -> ViewService:
    return ViewService(db=db)


@router.get("/filters/options")
async def list_graph_filter_options(
    request: Request,
    workspace_id: str,
    graph_names: list[str] | None = Query(default=None),
    subject_uri: str | None = Query(default=None),
    predicate_uri: str | None = Query(default=None),
    object_uri: str | None = Query(default=None),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphFilterOptionsResponse:
    await require_workspace_access(current_user.id, workspace_id)
    service = _get_view_service(request, db)
    try:
        data = await service.list_graph_filter_options(
            graph_names=graph_names,
            subject_uri=subject_uri,
            predicate_uri=predicate_uri,
            object_uri=object_uri,
        )
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphFilterOptionsResponse(
        subjects=[GraphFilterOption(**item) for item in data["subjects"]],
        predicates=[GraphFilterOption(**item) for item in data["predicates"]],
        objects=[GraphFilterOption(**item) for item in data["objects"]],
    )


@router.post("/filters/preview")
async def preview_graph_filters(
    request: Request,
    payload: TriplePreviewRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> TriplePreviewResponse:
    await require_workspace_access(current_user.id, payload.workspace_id)
    service = _get_view_service(request, db)
    try:
        data = await service.preview_graph_filters(
            graph_names=payload.graph_names,
            filters=[item.model_dump() for item in payload.filters],
            limit=payload.limit,
        )
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TriplePreviewResponse(
        count=int(data["count"]),
        individual_count=int(data["individual_count"]),
        object_properties_count=int(data["object_properties_count"]),
        data_properties_count=int(data["data_properties_count"]),
        rows=[TriplePreviewRow(**row) for row in data["rows"]],
    )


@router.get("/list")
async def list_views(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    user_id: str | None = Query(default=None, description="User context ID"),
    path: str | None = Query(default=None, description="Folder path filter ('' = root)"),
    recursive: bool = Query(default=False, description="Include views in subfolders"),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[GraphViewInfo]:
    _ = user_id
    await require_workspace_access(current_user.id, workspace_id)
    service = _get_view_service(request, db)
    try:
        views = await service.list_views(
            workspace_id=workspace_id, user_id=current_user.id, path=path, recursive=recursive
        )
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [GraphViewInfo(**item) for item in views]


@router.get("/folders")
async def list_folders(
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> FolderListResponse:
    await require_workspace_access(current_user.id, workspace_id)
    service = _get_view_service(request, db)
    try:
        folders = await service.list_folders(workspace_id=workspace_id, user_id=current_user.id)
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FolderListResponse(folders=[FolderNode(**f) for f in folders])


@router.put("/folders/rename")
async def rename_folder(
    request: Request,
    payload: RenameFolderRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> RenameFolderResponse:
    await require_workspace_access(current_user.id, payload.workspace_id)
    service = _get_view_service(request, db)
    try:
        res = await service.rename_folder(
            workspace_id=payload.workspace_id,
            from_path=payload.from_path,
            to_path=payload.to_path,
            merge=payload.merge,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RenameFolderResponse(**res)


@router.put("/{view_id}")
@router.patch("/{view_id}")
async def update_view(
    request: Request,
    view_id: str,
    payload: UpdateGraphView,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphViewInfo:
    """Update a view in place — rename, move folder, replace spec/state, change visibility."""
    await require_workspace_access(current_user.id, payload.workspace_id)
    service = _get_view_service(request, db)
    try:
        view = await service.update_view(
            view_id=view_id,
            workspace_id=payload.workspace_id,
            name=payload.name,
            path=payload.path,
            state=payload.state,
            visibility=payload.visibility,
            view_type=payload.view_type,
            kind=payload.kind,
            description=payload.description,
        )
    except ViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphViewInfo(**view)


@router.get("/{view_id}")
async def get_view(
    request: Request,
    view_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphViewInfo:
    _ = current_user
    service = _get_view_service(request, db)
    try:
        view = await service.get_view(view_id=view_id, workspace_id=workspace_id)
    except ViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphViewInfo(**view)


@router.post("")
@router.post("/")
async def create_view(
    request: Request,
    payload: CreateGraphView,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await require_workspace_access(current_user.id, payload.workspace_id)
    service = _get_view_service(request, db)
    try:
        return await service.create_view(
            workspace_id=payload.workspace_id,
            name=payload.name,
            view_type=payload.view_type,
            kind=payload.kind,
            visibility=payload.visibility,
            graph_id=payload.graph_id,
            graph_uri=payload.graph_uri,
            state=payload.state,
            creator=current_user.id,
            description=payload.description,
            graph_names=payload.graph_names,
            filters=[item.model_dump() for item in payload.filters],
            path=payload.path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{view_id}")
async def delete_view(
    request: Request,
    view_id: str,
    workspace_id: str | None = Query(default=None),
    payload: DeleteGraphView | None = None,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    effective_workspace_id = workspace_id or (payload.workspace_id if payload else None)
    if not effective_workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    await require_workspace_access(current_user.id, effective_workspace_id)
    service = _get_view_service(request, db)
    resolved = payload.uri if payload and payload.uri else view_id
    try:
        return await service.delete_view(resolved, workspace_id=effective_workspace_id)
    except ViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{view_id}/overview")
async def get_view_overview(
    request: Request,
    view_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> ViewOverview:
    await require_workspace_access(current_user.id, workspace_id)
    service = _get_view_service(request, db)
    try:
        overview = await service.get_view_overview(
            workspace_id=workspace_id,
            view_id=view_id,
            limit=limit,
        )
    except ViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ViewOverview(
        kpis=overview["kpis"],
        instances_by_class=overview["instances_by_class"],
    )


@router.get("/{view_id}/network")
async def get_view_network(
    request: Request,
    view_id: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    limit: int = Query(default=500, le=5000),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphData:
    _ = current_user
    service = _get_view_service(request, db)
    try:
        network = await service.get_view_network(
            workspace_id=workspace_id,
            view_id=view_id,
            limit=limit,
        )
    except ViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ViewServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphData(
        nodes=[
            GraphNode(
                id=node.id,
                workspace_id=node.workspace_id,
                type=node.type,
                label=node.label,
                properties=node.properties,
                created_at=node.created_at,
                updated_at=node.updated_at,
            )
            for node in network.nodes
        ],
        edges=[
            GraphEdge(
                id=edge.id,
                workspace_id=edge.workspace_id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                source_label=edge.source_label,
                target_label=edge.target_label,
                type=edge.type,
                properties=edge.properties,
                created_at=edge.created_at,
                updated_at=edge.updated_at,
            )
            for edge in network.edges
        ],
    )

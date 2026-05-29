"""FastAPI primary adapter for the analytics service.

Routes are intentionally thin: each one resolves a per-request
``AnalyticsService`` (storage-backed) and delegates to a single service
method. Read endpoints take a ``scenario_id`` query param and return the
matching slice of the prebuilt JSON — no aggregation or filtering happens
here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary import (
    AnalyticsSecondaryAdapterObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEvent,
    EventsResponse,
    IngestResponse,
    Metadata,
    OverviewResponse,
    PagesResponse,
    RebuildResponse,
    ScenariosResponse,
    SessionsResponse,
    UserDetail,
    UserDetailNotFound,
    UsersResponse,
    WorkspacesResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.service import (
    DEFAULT_SCENARIO_ID,
    AnalyticsService,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

router = APIRouter()


def _get_object_storage(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage
    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        storage = module.engine.services.object_storage
        request.app.state.object_storage = storage
        return storage
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Object storage is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def get_analytics_service(
    storage: ObjectStorageService = Depends(_get_object_storage),
) -> AnalyticsService:
    return AnalyticsService(
        storage=AnalyticsSecondaryAdapterObjectStorage(object_storage=storage)
    )


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


@router.post("/events", response_model=IngestResponse)
async def ingest_event(
    event: AnalyticsEvent,
    service: AnalyticsService = Depends(get_analytics_service),
) -> IngestResponse:
    stored_at = service.ingest_event(event)
    return IngestResponse(stored_at=stored_at)


@router.post("/rebuild", response_model=RebuildResponse)
async def rebuild_now(
    service: AnalyticsService = Depends(get_analytics_service),
) -> RebuildResponse:
    metadata = service.rebuild()
    return RebuildResponse(metadata=metadata)


@router.get("/metadata", response_model=Metadata | None)
async def get_metadata(
    service: AnalyticsService = Depends(get_analytics_service),
) -> Metadata | None:
    return service.get_metadata()


@router.get("/scenarios", response_model=ScenariosResponse)
async def get_scenarios(
    service: AnalyticsService = Depends(get_analytics_service),
) -> ScenariosResponse:
    return service.get_scenarios()


# ---------------------------------------------------------------------------
# Read path — each endpoint reads one slice of the matching prebuilt JSON
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> OverviewResponse:
    return service.get_overview(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/users", response_model=UsersResponse)
async def get_users(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> UsersResponse:
    return service.get_users(scenario_id=scenario_id, workspace_id=workspace_id)


@router.get("/users/{email:path}", response_model=UserDetail)
async def get_user_detail(
    email: str,
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> UserDetail:
    try:
        return service.get_user_detail(
            email, scenario_id=scenario_id, workspace_id=workspace_id
        )
    except UserDetailNotFound as exc:
        raise HTTPException(
            status_code=404, detail="No data for user in selected range"
        ) from exc


@router.get("/sessions", response_model=SessionsResponse)
async def get_sessions(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> SessionsResponse:
    return service.get_sessions(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/pages", response_model=PagesResponse)
async def get_pages(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> PagesResponse:
    return service.get_pages(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/workspaces", response_model=WorkspacesResponse)
async def get_workspaces(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> WorkspacesResponse:
    return service.get_workspaces(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/events", response_model=EventsResponse)
async def get_events(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    limit: int = Query(200, ge=1, le=1000),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> EventsResponse:
    return service.get_events(
        scenario_id=scenario_id,
        limit=limit,
        workspace_id=workspace_id,
        user_email=user_email,
    )

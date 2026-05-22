"""FastAPI primary adapter for the analytics service.

Thin transport layer: parses query parameters into
:class:`AnalyticsFilters`, calls the domain service, returns JSON.
Domain knows nothing about HTTP.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsFilters
from naas_abi.apps.nexus.apps.api.app.services.analytics.service import AnalyticsService


def build_router(service: AnalyticsService) -> APIRouter:
    """Build a FastAPI router bound to a configured :class:`AnalyticsService`.

    The router has no prefix; the caller mounts it under ``/analytics``
    (see :mod:`app.api.router`).
    """
    router = APIRouter()

    def _filters(
        start_date: str | None,
        end_date: str | None,
        user_email: str | None,
        workspace_id: str | None,
    ) -> AnalyticsFilters:
        return AnalyticsFilters.from_params(
            start_date=start_date,
            end_date=end_date,
            user_email=user_email,
            workspace_id=workspace_id,
        )

    @router.get("/health")
    def health() -> dict[str, Any]:
        rows = service.flat_events()
        return {"status": "ok", "events": len(rows)}

    @router.get("/overview")
    def overview(
        start_date: str | None = Query(None),
        end_date: str | None = Query(None),
        user_email: str | None = Query(None),
        workspace_id: str | None = Query(None),
    ) -> dict[str, Any]:
        return service.overview(_filters(start_date, end_date, user_email, workspace_id))

    @router.get("/users")
    def users(
        start_date: str | None = Query(None),
        end_date: str | None = Query(None),
        user_email: str | None = Query(None),
        workspace_id: str | None = Query(None),
    ) -> dict[str, Any]:
        return service.users(_filters(start_date, end_date, user_email, workspace_id))

    @router.get("/users/{email}")
    def user_detail(
        email: str,
        start_date: str | None = Query(None),
        end_date: str | None = Query(None),
        user_email: str | None = Query(None),
        workspace_id: str | None = Query(None),
    ) -> dict[str, Any]:
        detail = service.user_detail(
            email, _filters(start_date, end_date, user_email, workspace_id)
        )
        if detail is None:
            raise HTTPException(status_code=404, detail=f"User {email} has no events")
        return detail

    @router.get("/sessions")
    def sessions(
        start_date: str | None = Query(None),
        end_date: str | None = Query(None),
        user_email: str | None = Query(None),
        workspace_id: str | None = Query(None),
    ) -> dict[str, Any]:
        return service.sessions(_filters(start_date, end_date, user_email, workspace_id))

    @router.get("/pages")
    def pages(
        start_date: str | None = Query(None),
        end_date: str | None = Query(None),
        user_email: str | None = Query(None),
        workspace_id: str | None = Query(None),
    ) -> dict[str, Any]:
        return service.pages(_filters(start_date, end_date, user_email, workspace_id))

    @router.get("/workspaces")
    def workspaces(
        start_date: str | None = Query(None),
        end_date: str | None = Query(None),
        user_email: str | None = Query(None),
        workspace_id: str | None = Query(None),
    ) -> dict[str, Any]:
        return service.workspaces(_filters(start_date, end_date, user_email, workspace_id))

    @router.get("/events")
    def events(
        start_date: str | None = Query(None),
        end_date: str | None = Query(None),
        user_email: str | None = Query(None),
        workspace_id: str | None = Query(None),
        limit: int = Query(200, ge=1, le=2000),
    ) -> dict[str, Any]:
        return service.events(
            _filters(start_date, end_date, user_email, workspace_id), limit=limit
        )

    return router

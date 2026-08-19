"""
Conflict events router — wsr:ConflictZoneLoadingProcess HTTP interface.

Endpoint:
  GET /api/conflict-events — static list of Middle East conflict sites
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.conflict import conflict_service

router = APIRouter(tags=["conflict"])


@router.get("/api/conflict-events")
async def get_conflict_events() -> JSONResponse:
    data = conflict_service.get_events()
    return JSONResponse(
        content=[e.model_dump() for e in data],
        headers={"Cache-Control": "public, max-age=86400"},
    )

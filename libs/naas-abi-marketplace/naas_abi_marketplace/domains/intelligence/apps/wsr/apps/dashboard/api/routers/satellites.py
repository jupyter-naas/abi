"""
Satellites router — wsr:SatelliteTrackingProcess HTTP interface.

Endpoint:
  GET /api/satellites — active satellite TLE records (CelesTrak)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.satellites import satellite_service

router = APIRouter(tags=["satellites"])


@router.get("/api/satellites")
async def get_satellites() -> JSONResponse:
    data = await satellite_service.get_satellites()
    return JSONResponse(
        content=[s.model_dump() for s in data],
        headers={"Cache-Control": "public, max-age=3600"},
    )

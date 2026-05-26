"""
Earthquakes router — wsr:EarthquakeMonitoringProcess HTTP interface.

Endpoint:
  GET /api/earthquakes — M≥1.0 earthquakes in the past 24 hours (USGS)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.earthquakes import earthquake_service

router = APIRouter(tags=["earthquakes"])


@router.get("/api/earthquakes")
async def get_earthquakes() -> JSONResponse:
    data = await earthquake_service.get_earthquakes()
    return JSONResponse(
        content=[q.model_dump(by_alias=True) for q in data],
        headers={"Cache-Control": "public, max-age=300"},
    )

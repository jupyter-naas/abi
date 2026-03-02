"""
Flights router — wsr:FlightTrackingProcess HTTP interface.

Endpoints:
  GET /api/flights           — civil aviation (OpenSky)
  GET /api/military          — global military (ADSB.lol)
  GET /api/mideast-aircraft  — theater aircraft in Middle East (airplanes.live)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.flights import flight_service

router = APIRouter(tags=["flights"])


@router.get("/api/flights")
async def get_flights() -> JSONResponse:
    data = await flight_service.get_civil()
    return JSONResponse(
        content=[f.model_dump(by_alias=True) for f in data],
        headers={"Cache-Control": "public, max-age=30"},
    )


@router.get("/api/military")
async def get_military() -> JSONResponse:
    data = await flight_service.get_military()
    return JSONResponse(
        content=[f.model_dump(by_alias=True) for f in data],
        headers={"Cache-Control": "public, max-age=60"},
    )


@router.get("/api/mideast-aircraft")
async def get_mideast_aircraft() -> JSONResponse:
    data = await flight_service.get_theater()
    return JSONResponse(
        content=[f.model_dump(by_alias=True) for f in data],
        headers={"Cache-Control": "public, max-age=45"},
    )

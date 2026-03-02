"""
WSR FastAPI Service
BFO-grounded hexagonal data layer for the WSR globe.

Routers map 1:1 to BFO process types defined in wsr.ttl:
  /api/flights           → wv:FlightTrackingProcess
  /api/military          → wv:FlightTrackingProcess (military subtype)
  /api/mideast-aircraft  → wv:TheaterAircraftMonitoringProcess
  /api/satellites        → wv:SatelliteTrackingProcess
  /api/earthquakes       → wv:EarthquakeMonitoringProcess
  /api/news              → wv:NewsAggregationProcess
  /api/conflict-events   → wv:ConflictZoneLoadingProcess
  /api/cctv              → wv:CCTVStreamingProcess
  /api/cctv/snapshot     → wv:CCTVStreamingProcess (proxy)
  /api/webcams           → wv:CCTVStreamingProcess (OpenWebcamDB list)
  /api/webcams/stream    → wv:CCTVStreamingProcess (stream URL resolver)
"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.http_client import close_client, init_client
from routers import cctv, conflict, earthquakes, flights, news, satellites, webcams
from settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_client()
    yield
    await close_client()


app = FastAPI(
    title="WSR Data API",
    description="BFO-grounded geospatial intelligence data service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(flights.router)
app.include_router(satellites.router)
app.include_router(earthquakes.router)
app.include_router(news.router)
app.include_router(conflict.router)
app.include_router(cctv.router)
app.include_router(webcams.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "wsr-backend"}

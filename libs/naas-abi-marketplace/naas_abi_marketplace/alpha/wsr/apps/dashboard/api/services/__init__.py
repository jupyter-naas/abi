# WSR service layer — one self-contained service package per BFO process type.
# Routers import service singletons from here; adapters are never imported by routers.
from services.cctv import cctv_service
from services.conflict import conflict_service
from services.earthquakes import earthquake_service
from services.flights import flight_service
from services.news import news_service
from services.satellites import satellite_service
from services.webcams import webcam_service

__all__ = [
    "cctv_service",
    "conflict_service",
    "earthquake_service",
    "flight_service",
    "news_service",
    "satellite_service",
    "webcam_service",
]

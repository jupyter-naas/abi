"""
Airplanes.live adapter — Middle East theater aircraft.

Strategy: fan out 3 concurrent region queries (Iran, Levant, Gulf) and
deduplicate by icao24.
"""

import asyncio

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import FlightState
from services.flights.FlightsPort import IFlightAdapter

_BASE = "https://api.airplanes.live/v2/point"
_HEADERS = {"User-Agent": "WSR-Intel/1.0"}

_REGIONS = [
    {"lat": 32, "lon": 53, "radius": 500},
    {"lat": 32, "lon": 35, "radius": 300},
    {"lat": 25, "lon": 52, "radius": 200},
]

_FT_TO_M     = 0.3048
_KNOTS_TO_MS = 0.514444


class AirplanesLiveAdapter(IFlightAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[FlightState]] = TTLCache(ttl_seconds=45)

    async def fetch(self) -> list[FlightState]:
        return await self._cache.get_or_fetch("theater", self._fetch)

    async def _fetch(self) -> list[FlightState]:
        tasks = [self._query_region(**r) for r in _REGIONS]
        region_results = await asyncio.gather(*tasks, return_exceptions=False)

        seen: set[str] = set()
        merged: list[FlightState] = []
        for region in region_results:
            for flight in region:
                if flight.icao24 not in seen:
                    seen.add(flight.icao24)
                    merged.append(flight)
        return merged

    async def _query_region(self, lat: int, lon: int, radius: int) -> list[FlightState]:
        try:
            resp = await get_client().get(
                f"{_BASE}/{lat}/{lon}/{radius}",
                headers=_HEADERS, timeout=8,
            )
            if not resp.is_success:
                return []
            result: list[FlightState] = []
            for a in resp.json().get("ac") or []:
                a_lat, a_lon = a.get("lat"), a.get("lon")
                if a_lat is None or a_lon is None:
                    continue
                alt_baro = a.get("alt_baro", 0)
                result.append(FlightState(
                    icao24=a.get("hex", ""),
                    callsign=(a.get("flight") or "").strip() or a.get("hex", ""),
                    lat=float(a_lat), lon=float(a_lon),
                    altitude=float(alt_baro) * _FT_TO_M if isinstance(alt_baro, (int, float)) else 0.0,
                    velocity=float(a.get("gs") or 0) * _KNOTS_TO_MS,
                    heading=float(a.get("track") or 0),
                    onGround=False,
                    isMilitary=bool(a.get("military")),
                ))
            return result
        except Exception:
            return []

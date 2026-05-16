"""
ADSB.lol adapter — global military aircraft.

Primary:  https://api.adsb.lol/v2/mil
Fallback: https://api.airplanes.live/v2/mil (same schema)
"""

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import FlightState
from services.flights.FlightsPort import IFlightAdapter

_ADSB_LOL_URL      = "https://api.adsb.lol/v2/mil"
_AIRPLANES_LIVE_URL = "https://api.airplanes.live/v2/mil"
_HEADERS = {"User-Agent": "WSR-Intel/1.0 (geospatial-intelligence-platform)"}

_FT_TO_M     = 0.3048
_KNOTS_TO_MS = 0.514444


def _parse(aircraft: list[dict]) -> list[FlightState]:
    result: list[FlightState] = []
    for a in aircraft:
        lat, lon = a.get("lat"), a.get("lon")
        if lat is None or lon is None:
            continue
        alt_baro = a.get("alt_baro", 0)
        result.append(FlightState(
            icao24=a.get("hex", ""),
            callsign=(a.get("flight") or "").strip() or a.get("hex", ""),
            lat=float(lat), lon=float(lon),
            altitude=float(alt_baro) * _FT_TO_M if isinstance(alt_baro, (int, float)) else 0.0,
            velocity=float(a.get("gs") or 0) * _KNOTS_TO_MS,
            heading=float(a.get("track") or 0),
            onGround=False,
            isMilitary=True,
        ))
    return result


class ADSBLolAdapter(IFlightAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[FlightState]] = TTLCache(ttl_seconds=60)

    async def fetch(self) -> list[FlightState]:
        return await self._cache.get_or_fetch("military", self._fetch)

    async def _fetch(self) -> list[FlightState]:
        client = get_client()
        try:
            resp = await client.get(_ADSB_LOL_URL, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            aircraft: list[dict] = resp.json().get("ac") or []
            if aircraft:
                return _parse(aircraft)
        except Exception:
            pass
        try:
            resp = await client.get(_AIRPLANES_LIVE_URL, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            return _parse(resp.json().get("ac") or [])
        except Exception:
            return []

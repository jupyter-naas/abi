"""
OpenSky Network adapter — civil flight tracking.

Auth priority (first available wins):
  1. OAuth2 client credentials  — new accounts (mid-March 2025+)
  2. Legacy basic auth          — pre-March 2025 accounts
  3. Anonymous                  — 400 API credits/day; falls back to airplanes.live tiles

Fallback: airplanes.live /v2/point tiled queries (8 strategic regions, no auth needed).
"""

import asyncio
import base64
import logging
import time

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import FlightState
from services.flights.FlightsPort import IFlightAdapter
from settings import settings

log = logging.getLogger(__name__)

_OPENSKY_URL    = "https://opensky-network.org/api/states/all"
_TOKEN_URL      = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
_AIRPLANES_BASE = "https://api.airplanes.live/v2/point"
_HEADERS        = {"User-Agent": "WSR-Intel/1.0 (geospatial-intelligence-platform)"}

_FT_TO_M     = 0.3048
_KNOTS_TO_MS = 0.514444

_GLOBAL_TILES = [
    (51,  -30, 500),
    (40,  -95, 500),
    (50,   15, 500),
    (35,  120, 500),
    (25,   70, 500),
    (-10, 130, 500),
    (-15, -55, 500),
    (  5,  25, 500),
]


class OpenSkyAdapter(IFlightAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[FlightState]] = TTLCache(ttl_seconds=30)
        self._token: str = ""
        self._token_expires_at: float = 0.0

    async def fetch(self) -> list[FlightState]:
        return await self._cache.get_or_fetch("flights", self._fetch)

    async def _fetch(self) -> list[FlightState]:
        try:
            data = await self._fetch_opensky()
            if data:
                return data
            log.debug("[opensky] empty response — falling back to airplanes.live")
        except Exception as exc:
            log.info("[opensky] failed (%s) — falling back to airplanes.live", exc)
        return await self._fetch_airplanes_live()

    async def _get_oauth2_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        client = get_client()
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     settings.opensky_client_id,
                "client_secret": settings.opensky_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._token_expires_at = time.monotonic() + int(body.get("expires_in", 1800)) - 60
        return self._token

    async def _fetch_opensky(self) -> list[FlightState]:
        headers = dict(_HEADERS)
        if settings.opensky_client_id and settings.opensky_client_secret:
            headers["Authorization"] = f"Bearer {await self._get_oauth2_token()}"
        elif settings.opensky_username and settings.opensky_password:
            token = base64.b64encode(
                f"{settings.opensky_username}:{settings.opensky_password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {token}"

        resp = await get_client().get(_OPENSKY_URL, headers=headers, timeout=12)
        resp.raise_for_status()

        result: list[FlightState] = []
        for s in resp.json().get("states") or []:
            lon, lat = s[5], s[6]
            if lon is None or lat is None:
                continue
            result.append(FlightState(
                icao24=s[0] or "",
                callsign=(s[1] or "").strip() or (s[0] or ""),
                lat=float(lat), lon=float(lon),
                altitude=float(s[7] or 0),
                velocity=float(s[9] or 0),
                heading=float(s[10] or 0),
                onGround=bool(s[8]),
            ))
        return result

    async def _query_tile(self, lat: int, lon: int, radius: int) -> list[FlightState]:
        try:
            resp = await get_client().get(
                f"{_AIRPLANES_BASE}/{lat}/{lon}/{radius}",
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
                    onGround=bool(a.get("onGround", False)),
                ))
            return result
        except Exception:
            return []

    async def _fetch_airplanes_live(self) -> list[FlightState]:
        tile_results = await asyncio.gather(*[self._query_tile(*t) for t in _GLOBAL_TILES])
        seen: set[str] = set()
        merged: list[FlightState] = []
        for tile in tile_results:
            for f in tile:
                if f.icao24 not in seen:
                    seen.add(f.icao24)
                    merged.append(f)
        return merged

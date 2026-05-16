"""
USGS Earthquake adapter — M≥1.0 earthquakes in the past 24 hours.

Source: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson
GeoJSON coordinate order: [longitude, latitude, depth_km]
"""

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import EarthquakeFeature
from services.earthquakes.EarthquakesPort import IEarthquakeAdapter

_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"


class USGSAdapter(IEarthquakeAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[EarthquakeFeature]] = TTLCache(ttl_seconds=300)

    async def fetch(self) -> list[EarthquakeFeature]:
        return await self._cache.get_or_fetch("earthquakes", self._fetch)

    async def _fetch(self) -> list[EarthquakeFeature]:
        resp = await get_client().get(_URL, timeout=8)
        resp.raise_for_status()

        result: list[EarthquakeFeature] = []
        for f in resp.json().get("features") or []:
            props = f.get("properties", {})
            mag = props.get("mag")
            if mag is None or float(mag) < 1.0:
                continue
            coords = f.get("geometry", {}).get("coordinates", [0, 0, 0])
            result.append(EarthquakeFeature(
                id=f["id"],
                mag=float(mag),
                place=props.get("place") or "",
                lon=float(coords[0]),
                lat=float(coords[1]),
                depth=float(coords[2]),
                time=int(props.get("time") or 0),
            ))
        return result

"""
511NY.org CCTV adapter — New York City traffic cameras.

Source: https://511ny.org/api/getcameras?key=&format=json
Filter: Manhattan + surrounding boroughs bounding box, non-disabled, has VideoUrl.
Cap: 150 cameras.
"""

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import CCTVCamera
from services.cctv.CCTVPort import ICCTVAdapter

_URL = "https://511ny.org/api/getcameras?key=&format=json"
_BOUNDS = dict(min_lat=40.60, max_lat=40.90, min_lon=-74.05, max_lon=-73.70)


class NYCAdapter(ICCTVAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[CCTVCamera]] = TTLCache(ttl_seconds=300)

    async def fetch(self) -> list[CCTVCamera]:
        return await self._cache.get_or_fetch("nyc", self._fetch)

    async def _fetch(self) -> list[CCTVCamera]:
        client = get_client()
        resp = await client.get(_URL, timeout=8)
        if not resp.is_success:
            return []

        result: list[CCTVCamera] = []
        for c in resp.json():
            lat, lon = c.get("Latitude"), c.get("Longitude")
            if lat is None or lon is None:
                continue
            if c.get("Disabled") or c.get("Blocked"):
                continue
            video_url = c.get("VideoUrl") or ""
            if not video_url:
                continue
            if not (
                _BOUNDS["min_lat"] <= lat <= _BOUNDS["max_lat"]
                and _BOUNDS["min_lon"] <= lon <= _BOUNDS["max_lon"]
            ):
                continue

            result.append(
                CCTVCamera(
                    id=f"nyc-{c['ID']}",
                    name=c.get("Name", ""),
                    lat=float(lat), lon=float(lon),
                    city="New York", country="USA",
                    imageUrl="",
                    videoUrl=video_url,
                    type="hls",
                    source="nyc",
                )
            )
            if len(result) >= 150:
                break

        return result

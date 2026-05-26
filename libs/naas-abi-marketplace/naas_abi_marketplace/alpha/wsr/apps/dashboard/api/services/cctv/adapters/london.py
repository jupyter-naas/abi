"""
TfL JamCam adapter — all publicly accessible London traffic cameras.

Source:  https://api.tfl.gov.uk/Place/Type/JamCam
Docs:    https://api-portal.tfl.gov.uk/
Auth:    Optional TFL_APP_KEY env var (60 → 500 req/min).
         Register free at https://api-portal.tfl.gov.uk/signup

TfL returns ~900 JamCam records in a single response (no pagination).
Available cameras serve a public JPEG snapshot refreshed every ~30 s.
"""

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import CCTVCamera
from services.cctv.CCTVPort import ICCTVAdapter
from settings import settings

_URL = "https://api.tfl.gov.uk/Place/Type/JamCam"


class LondonAdapter(ICCTVAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[CCTVCamera]] = TTLCache(ttl_seconds=300)

    async def fetch(self) -> list[CCTVCamera]:
        return await self._cache.get_or_fetch("london", self._fetch)

    def _params(self) -> dict[str, str]:
        key = settings.tfl_app_key.strip()
        return {"app_key": key} if key else {}

    async def _fetch(self) -> list[CCTVCamera]:
        client = get_client()
        resp = await client.get(
            _URL,
            params=self._params(),
            timeout=15,
            headers={"User-Agent": "WSR-Intel/1.0 (geospatial-intelligence-platform)"},
        )
        if not resp.is_success:
            return []

        result: list[CCTVCamera] = []
        for cam in resp.json():
            lat, lon = cam.get("lat"), cam.get("lon")
            if lat is None or lon is None:
                continue

            props: list[dict] = cam.get("additionalProperties") or []
            prop_map = {p["key"]: p["value"] for p in props}

            if prop_map.get("available", "true").lower() == "false":
                continue

            img_url = prop_map.get("imageUrl", "")
            if not img_url:
                continue

            result.append(
                CCTVCamera(
                    id=f"lon-{cam['id']}",
                    name=cam.get("commonName", ""),
                    lat=float(lat), lon=float(lon),
                    city="London", country="UK",
                    imageUrl=img_url,
                    videoUrl=img_url,
                    type="hls",
                    source="london",
                )
            )

        return result

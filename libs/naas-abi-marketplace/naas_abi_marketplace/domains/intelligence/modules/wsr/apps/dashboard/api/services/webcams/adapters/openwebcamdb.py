"""
OpenWebcamDB adapter.

Endpoints used:
  GET /webcams          → paginated list (1 page × 50, cached 1 h)
  GET /webcams/{slug}   → stream URL resolution (cached 30 min)

Requires OPENWEBCAMDB_API_KEY. Returns [] if absent.
Free tier rate limit: 5 req/min — enforced by the 1-hour list cache.
"""

import re

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import CCTVCamera, StreamResult
from services.webcams.WebcamsPort import IWebcamAdapter
from settings import settings

_BASE = "https://openwebcamdb.com/api/v1"

_YT_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|live/|embed/))([A-Za-z0-9_-]{11})"
)


def _youtube_video_id(url: str) -> str | None:
    m = _YT_RE.search(url)
    return m.group(1) if m else None


def _resolve_embed_url(raw: str, stream_type: str) -> StreamResult:
    vid = _youtube_video_id(raw)
    if stream_type == "youtube" or vid:
        url = (
            f"https://www.youtube.com/embed/{vid}?autoplay=1&mute=1&controls=1"
            if vid
            else raw
        )
        return StreamResult(url=url, type="youtube")
    return StreamResult(url=raw, type="youtube")


class OpenWebcamDBAdapter(IWebcamAdapter):
    def __init__(self) -> None:
        self._list_cache:   TTLCache[list[CCTVCamera]] = TTLCache(ttl_seconds=3600)
        self._stream_cache: TTLCache[StreamResult]     = TTLCache(ttl_seconds=1800)

    def _auth_headers(self) -> dict[str, str]:
        key = settings.openwebcamdb_api_key.strip().strip('"')
        return {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    async def fetch_list(self) -> list[CCTVCamera]:
        if not settings.openwebcamdb_api_key:
            return []
        return await self._list_cache.get_or_fetch("list", self._fetch_list)

    async def _fetch_list(self) -> list[CCTVCamera]:
        client = get_client()
        resp = await client.get(
            f"{_BASE}/webcams",
            params={"per_page": 50, "page": 1},
            headers=self._auth_headers(),
            timeout=12,
        )
        if not resp.is_success:
            return []

        result: list[CCTVCamera] = []
        for w in resp.json().get("data") or []:
            try:
                lat = float(w.get("latitude", "nan"))
                lon = float(w.get("longitude", "nan"))
            except ValueError:
                continue
            if lat != lat or lon != lon:
                continue

            country_info = w.get("country") or {}
            result.append(
                CCTVCamera(
                    id=f"owdb-{w['slug']}",
                    slug=w.get("slug"),
                    name=w.get("title", ""),
                    lat=lat, lon=lon,
                    city=w.get("city") or country_info.get("name") or "Unknown",
                    country=country_info.get("name"),
                    imageUrl=w.get("thumbnail_url") or "",
                    videoUrl="",
                    type="youtube",
                    source="openwebcamdb",
                )
            )
        return result

    async def fetch_stream(self, slug: str) -> StreamResult:
        return await self._stream_cache.get_or_fetch(slug, lambda: self._fetch_stream(slug))

    async def _fetch_stream(self, slug: str) -> StreamResult:
        client = get_client()
        resp = await client.get(
            f"{_BASE}/webcams/{slug}",
            headers=self._auth_headers(),
            timeout=8,
        )
        resp.raise_for_status()
        detail = resp.json().get("data") or {}
        raw = detail.get("stream_url") or ""
        stream_type = detail.get("stream_type") or "iframe"
        if not raw:
            raise ValueError("no stream_url in response")
        return _resolve_embed_url(raw, stream_type)

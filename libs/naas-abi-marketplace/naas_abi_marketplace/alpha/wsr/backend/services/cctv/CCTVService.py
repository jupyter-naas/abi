"""
CCTVService — wsr:CCTVStreamingProcess orchestrator.

Fan-out to all source adapters, merge results, fall back to static theater
cameras if dynamic sources fail. Also owns the HLS/JPEG snapshot proxy.
"""

import asyncio
import logging

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import CCTVCamera
from services.cctv.CCTVPort import ICCTVAdapter, ICCTVService
from services.cctv.adapters.london import LondonAdapter
from services.cctv.adapters.mideast import MideastAdapter
from services.cctv.adapters.nyc import NYCAdapter
from services.webcams.adapters.openwebcamdb import OpenWebcamDBAdapter

log = logging.getLogger(__name__)

_snap_cache: TTLCache[tuple[bytes, str]] = TTLCache(ttl_seconds=4, max_size=500)


class CCTVService(ICCTVService):
    def __init__(self, adapters: list[ICCTVAdapter]) -> None:
        self._adapters = adapters
        self._static = MideastAdapter()

    async def get_cameras(self) -> list[CCTVCamera]:
        try:
            results = await asyncio.gather(
                *(a.fetch() for a in self._adapters),
                return_exceptions=False,
            )
            return [cam for batch in results for cam in batch]
        except Exception as exc:
            log.warning("[cctv] dynamic fetch failed, serving static fallback: %s", exc)
            return await self._static.fetch()

    async def proxy_snapshot(self, url: str) -> tuple[bytes, str]:
        return await _snap_cache.get_or_fetch(url, lambda: self._fetch_snapshot(url))

    async def _fetch_snapshot(self, url: str) -> tuple[bytes, str]:
        fetch_url = url

        if url.endswith(".m3u8"):
            client = get_client()
            m3u8_resp = await client.get(url, timeout=5)
            if not m3u8_resp.is_success:
                raise ValueError("HLS playlist fetch failed")
            lines = [
                ln.strip()
                for ln in m3u8_resp.text.splitlines()
                if ln.strip() and not ln.startswith("#")
            ]
            if not lines:
                raise ValueError("empty HLS playlist")
            segment = lines[-1]
            base = url[: url.rfind("/") + 1]
            fetch_url = segment if segment.startswith("http") else base + segment

        client = get_client()
        resp = await client.get(fetch_url, timeout=6)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "application/octet-stream")

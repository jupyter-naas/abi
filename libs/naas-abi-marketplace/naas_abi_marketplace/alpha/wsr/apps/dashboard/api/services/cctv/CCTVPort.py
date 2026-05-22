"""
CCTV port — wsr:CCTVStreamingProcess interface contracts.

ICCTVAdapter  — contract every source adapter must satisfy.
ICCTVService  — contract the service provides to routers.
"""

from ports.models import CCTVCamera


class ICCTVAdapter:
    """Secondary port: a single CCTV data source."""

    async def fetch(self) -> list[CCTVCamera]:
        raise NotImplementedError


class ICCTVService:
    """Primary port: what routers call."""

    async def get_cameras(self) -> list[CCTVCamera]:
        raise NotImplementedError

    async def proxy_snapshot(self, url: str) -> tuple[bytes, str]:
        raise NotImplementedError

"""
CCTV port — abi:CCTVStreamingProcess interface contracts.

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

    async def proxy_snapshot(self, camera_id: str, kind: str) -> tuple[bytes, str]:
        """The current image (``kind="image"``) or stream (``"video"``) of one
        camera of ``get_cameras()``, by its id."""
        raise NotImplementedError

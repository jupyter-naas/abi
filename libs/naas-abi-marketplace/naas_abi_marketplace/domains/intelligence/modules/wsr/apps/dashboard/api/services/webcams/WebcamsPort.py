"""
Webcams port — wsr:CCTVStreamingProcess (OpenWebcamDB) interface contracts.
"""

from ports.models import CCTVCamera, StreamResult


class IWebcamAdapter:
    async def fetch_list(self) -> list[CCTVCamera]:
        raise NotImplementedError

    async def fetch_stream(self, slug: str) -> StreamResult:
        raise NotImplementedError


class IWebcamsService:
    @property
    def is_configured(self) -> bool:
        raise NotImplementedError

    async def get_webcams(self) -> list[CCTVCamera]:
        raise NotImplementedError

    async def get_stream_url(self, slug: str) -> StreamResult:
        raise NotImplementedError

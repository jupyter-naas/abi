"""
WebcamsService — wsr:CCTVStreamingProcess (OpenWebcamDB) orchestrator.
"""

from ports.models import CCTVCamera, StreamResult
from services.webcams.WebcamsPort import IWebcamAdapter, IWebcamsService
from settings import settings


class WebcamsService(IWebcamsService):
    def __init__(self, adapter: IWebcamAdapter) -> None:
        self._adapter = adapter

    @property
    def is_configured(self) -> bool:
        return bool(settings.openwebcamdb_api_key)

    async def get_webcams(self) -> list[CCTVCamera]:
        return await self._adapter.fetch_list()

    async def get_stream_url(self, slug: str) -> StreamResult:
        return await self._adapter.fetch_stream(slug)

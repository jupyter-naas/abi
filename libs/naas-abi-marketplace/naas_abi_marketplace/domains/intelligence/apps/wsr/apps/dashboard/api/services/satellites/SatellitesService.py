import logging

from ports.models import SatelliteRecord
from services.satellites.SatellitesPort import ISatelliteAdapter, ISatellitesService

log = logging.getLogger(__name__)


class SatellitesService(ISatellitesService):
    def __init__(self, adapter: ISatelliteAdapter) -> None:
        self._adapter = adapter

    async def get_satellites(self) -> list[SatelliteRecord]:
        try:
            return await self._adapter.fetch()
        except Exception as exc:
            log.warning("[satellites] fetch failed: %s", exc)
            return []

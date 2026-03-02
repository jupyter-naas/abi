import logging

from ports.models import EarthquakeFeature
from services.earthquakes.EarthquakesPort import IEarthquakeAdapter, IEarthquakesService

log = logging.getLogger(__name__)


class EarthquakesService(IEarthquakesService):
    def __init__(self, adapter: IEarthquakeAdapter) -> None:
        self._adapter = adapter

    async def get_earthquakes(self) -> list[EarthquakeFeature]:
        try:
            return await self._adapter.fetch()
        except Exception as exc:
            log.warning("[earthquakes] fetch failed: %s", exc)
            return []

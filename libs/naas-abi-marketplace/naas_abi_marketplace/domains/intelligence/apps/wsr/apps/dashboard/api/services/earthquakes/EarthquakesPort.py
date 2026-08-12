from ports.models import EarthquakeFeature


class IEarthquakeAdapter:
    async def fetch(self) -> list[EarthquakeFeature]:
        raise NotImplementedError


class IEarthquakesService:
    async def get_earthquakes(self) -> list[EarthquakeFeature]:
        raise NotImplementedError

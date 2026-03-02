from ports.models import SatelliteRecord


class ISatelliteAdapter:
    async def fetch(self) -> list[SatelliteRecord]:
        raise NotImplementedError


class ISatellitesService:
    async def get_satellites(self) -> list[SatelliteRecord]:
        raise NotImplementedError

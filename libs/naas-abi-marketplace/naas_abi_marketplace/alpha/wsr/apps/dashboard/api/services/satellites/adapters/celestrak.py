"""
CelesTrak TLE adapter — active satellite catalogue.

Source: https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=TLE
Cache TTL: 1 hour (CelesTrak updates catalogue daily).
"""

from core.cache import TTLCache
from core.http_client import get_client
from ports.models import SatelliteRecord
from services.satellites.SatellitesPort import ISatelliteAdapter

_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=TLE"


class CelesTrakAdapter(ISatelliteAdapter):
    def __init__(self) -> None:
        self._cache: TTLCache[list[SatelliteRecord]] = TTLCache(ttl_seconds=3600)

    async def fetch(self) -> list[SatelliteRecord]:
        return await self._cache.get_or_fetch("satellites", self._fetch)

    async def _fetch(self) -> list[SatelliteRecord]:
        resp = await get_client().get(_URL, timeout=30)
        resp.raise_for_status()

        lines = [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
        records: list[SatelliteRecord] = []
        i = 0
        while i + 2 < len(lines):
            name, line1, line2 = lines[i], lines[i + 1], lines[i + 2]
            if line1.startswith("1 ") and line2.startswith("2 "):
                records.append(SatelliteRecord(name=name, line1=line1, line2=line2))
            i += 3
        return records

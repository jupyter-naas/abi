"""
FlightsService — wsr:FlightTrackingProcess orchestrator.
"""

import logging

from ports.models import FlightState
from services.flights.FlightsPort import IFlightAdapter, IFlightsService

log = logging.getLogger(__name__)


class FlightsService(IFlightsService):
    def __init__(
        self,
        civil: IFlightAdapter,
        military: IFlightAdapter,
        theater: IFlightAdapter,
    ) -> None:
        self._civil    = civil
        self._military = military
        self._theater  = theater

    async def get_civil(self) -> list[FlightState]:
        try:
            return await self._civil.fetch()
        except Exception as exc:
            log.warning("[flights/civil] fetch failed: %s", exc)
            return []

    async def get_military(self) -> list[FlightState]:
        try:
            return await self._military.fetch()
        except Exception as exc:
            log.warning("[flights/military] fetch failed: %s", exc)
            return []

    async def get_theater(self) -> list[FlightState]:
        try:
            return await self._theater.fetch()
        except Exception as exc:
            log.warning("[flights/theater] fetch failed: %s", exc)
            return []

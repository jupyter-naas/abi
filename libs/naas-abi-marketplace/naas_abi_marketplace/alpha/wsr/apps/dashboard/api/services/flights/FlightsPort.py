"""
Flights port — wsr:FlightTrackingProcess interface contracts.
"""

from ports.models import FlightState


class IFlightAdapter:
    async def fetch(self) -> list[FlightState]:
        raise NotImplementedError


class IFlightsService:
    async def get_civil(self) -> list[FlightState]:
        raise NotImplementedError

    async def get_military(self) -> list[FlightState]:
        raise NotImplementedError

    async def get_theater(self) -> list[FlightState]:
        raise NotImplementedError

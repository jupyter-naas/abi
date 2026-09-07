from services.flights.adapters.adsb_lol import ADSBLolAdapter
from services.flights.adapters.airplanes_live import AirplanesLiveAdapter
from services.flights.adapters.opensky import OpenSkyAdapter
from services.flights.FlightsService import FlightsService

flight_service = FlightsService(
    civil=OpenSkyAdapter(),
    military=ADSBLolAdapter(),
    theater=AirplanesLiveAdapter(),
)

__all__ = ["flight_service"]

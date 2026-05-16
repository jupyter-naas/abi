from services.satellites.adapters.celestrak import CelesTrakAdapter
from services.satellites.SatellitesService import SatellitesService

satellite_service = SatellitesService(adapter=CelesTrakAdapter())

__all__ = ["satellite_service"]

from services.earthquakes.adapters.usgs import USGSAdapter
from services.earthquakes.EarthquakesService import EarthquakesService

earthquake_service = EarthquakesService(adapter=USGSAdapter())

__all__ = ["earthquake_service"]

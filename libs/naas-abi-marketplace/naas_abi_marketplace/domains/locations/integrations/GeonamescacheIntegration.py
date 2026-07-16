from dataclasses import dataclass
from typing import Any, List, Optional

import geonamescache
from langchain_core.tools import StructuredTool
from naas_abi_core.integration import Integration
from naas_abi_core.integration.integration import IntegrationConfiguration
from pydantic import BaseModel, Field


@dataclass
class GeonamescacheIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the geonamescache integration."""

    pass


class GeonamescacheIntegration(Integration):
    """Integration with geonamescache (https://github.com/yaph/geonamescache), a
    bundled offline snapshot of GeoNames countries, US states/counties and cities.
    No network access or download is required.
    """

    __configuration: GeonamescacheIntegrationConfiguration

    def __init__(self, configuration: GeonamescacheIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__cache = geonamescache.GeonamesCache()

    def get_countries(self) -> List[Any]:
        """Get all countries with ISO codes, capital, continent and population.

        Returns:
            List of country dicts.
        """
        return list(self.__cache.get_countries().values())

    def get_cities(self, min_population: Optional[int] = None) -> List[Any]:
        """Get cities, optionally filtered by minimum population.

        Args:
            min_population: Only return cities with at least this population.

        Returns:
            List of city dicts (name, countrycode, population, latitude,
            longitude, admin1code).
        """
        cities = list(self.__cache.get_cities().values())
        if min_population is not None:
            cities = [c for c in cities if c.get("population", 0) >= min_population]
        return cities

    def search_cities(self, name: str, case_sensitive: bool = False) -> List[Any]:
        """Search cities by (partial) name.

        Args:
            name: City name or substring to search for.
            case_sensitive: Whether the search should be case sensitive.

        Returns:
            List of matching city dicts.
        """
        return self.__cache.search_cities(name, case_sensitive=case_sensitive)

    def get_us_states(self) -> List[Any]:
        """Get US states.

        Returns:
            List of US state dicts.
        """
        return list(self.__cache.get_us_states().values())

    def get_us_counties(self) -> List[Any]:
        """Get US counties.

        Returns:
            List of US county dicts.
        """
        return list(self.__cache.get_us_counties())

    @staticmethod
    def as_tools(
        configuration: GeonamescacheIntegrationConfiguration,
    ) -> List[StructuredTool]:
        """Get tools for the geonamescache integration.

        Args:
            configuration: geonamescache integration configuration.

        Returns:
            List of tools.
        """
        integration = GeonamescacheIntegration(configuration)

        class GetCountriesParameters(BaseModel):
            pass

        class GetCitiesParameters(BaseModel):
            min_population: Optional[int] = Field(
                default=None, description="Only return cities with at least this population."
            )

        class SearchCitiesParameters(BaseModel):
            name: str = Field(..., description="City name or substring to search for.")

        class GetUsStatesParameters(BaseModel):
            pass

        class GetUsCountiesParameters(BaseModel):
            pass

        return [
            StructuredTool(
                name="get_geonamescache_countries",
                description="Get all countries (ISO code, capital, continent, population) from geonamescache",
                func=lambda **kwargs: integration.get_countries(),
                args_schema=GetCountriesParameters,
            ),
            StructuredTool(
                name="get_geonamescache_cities",
                description="Get cities, optionally filtered by minimum population, from geonamescache",
                func=lambda **kwargs: integration.get_cities(**kwargs),
                args_schema=GetCitiesParameters,
            ),
            StructuredTool(
                name="search_geonamescache_cities",
                description="Search cities by name from geonamescache",
                func=lambda **kwargs: integration.search_cities(**kwargs),
                args_schema=SearchCitiesParameters,
            ),
            StructuredTool(
                name="get_geonamescache_us_states",
                description="Get US states from geonamescache",
                func=lambda **kwargs: integration.get_us_states(),
                args_schema=GetUsStatesParameters,
            ),
            StructuredTool(
                name="get_geonamescache_us_counties",
                description="Get US counties from geonamescache",
                func=lambda **kwargs: integration.get_us_counties(),
                args_schema=GetUsCountiesParameters,
            ),
        ]

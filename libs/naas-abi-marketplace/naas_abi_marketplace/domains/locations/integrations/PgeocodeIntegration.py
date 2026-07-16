from dataclasses import dataclass
from typing import Dict, List, Union

import pandas as pd
import pgeocode
from langchain_core.tools import StructuredTool
from naas_abi_core.integration import Integration
from naas_abi_core.integration.integration import (
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from pydantic import BaseModel, Field


@dataclass
class PgeocodeIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the pgeocode integration."""

    pass


class PgeocodeIntegration(Integration):
    """Integration with pgeocode (https://github.com/symerio/pgeocode), an offline
    postal-code geocoder covering ~83 countries. Data is downloaded once per
    country and cached locally by the pgeocode library itself.
    """

    __configuration: PgeocodeIntegrationConfiguration

    def __init__(self, configuration: PgeocodeIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__geocoders: Dict[str, pgeocode.Nominatim] = {}

    def __get_geocoder(self, country_code: str) -> pgeocode.Nominatim:
        country_code = country_code.upper()
        if country_code not in self.__geocoders:
            try:
                self.__geocoders[country_code] = pgeocode.Nominatim(country_code)
            except Exception as e:
                raise IntegrationConnectionError(
                    f"Failed to load pgeocode data for {country_code}: {str(e)}"
                ) from e
        return self.__geocoders[country_code]

    def query_postal_code(
        self, country_code: str, postal_code: Union[str, List[str]]
    ) -> List[dict]:
        """Look up city/region/state for one or more postal codes.

        Args:
            country_code: ISO-3166 alpha-2 country code (e.g. "US").
            postal_code: A postal code, or a list of postal codes.

        Returns:
            List of dicts with city, region, state, country_code, postal_code,
            latitude, longitude.
        """
        geocoder = self.__get_geocoder(country_code)
        result = geocoder.query_postal_code(postal_code)
        df = result.to_frame().T if isinstance(result, pd.Series) else result.copy()
        df = df.rename(
            columns={
                "place_name": "city",
                "state_name": "state",
                "county_name": "region",
            }
        )
        records = df[
            ["city", "region", "state", "country_code", "postal_code", "latitude", "longitude"]
        ].to_dict(orient="records")
        for record in records:
            for key, value in record.items():
                if isinstance(value, float) and pd.isna(value):
                    record[key] = None
        return records

    @staticmethod
    def as_tools(configuration: PgeocodeIntegrationConfiguration) -> List[StructuredTool]:
        """Get tools for the pgeocode integration.

        Args:
            configuration: pgeocode integration configuration.

        Returns:
            List of tools.
        """
        integration = PgeocodeIntegration(configuration)

        class QueryPostalCodeParameters(BaseModel):
            country_code: str = Field(..., description="ISO-3166 alpha-2 country code, e.g. 'US'.")
            postal_code: str = Field(..., description="Postal code to look up.")

        return [
            StructuredTool(
                name="query_pgeocode_postal_code",
                description="Look up city/region/state for a postal code using pgeocode (offline, ~83 countries)",
                func=lambda **kwargs: integration.query_postal_code(**kwargs),
                args_schema=QueryPostalCodeParameters,
            ),
        ]

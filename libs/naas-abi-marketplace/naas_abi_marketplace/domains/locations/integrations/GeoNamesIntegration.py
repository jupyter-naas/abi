import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests
from langchain_core.tools import StructuredTool
from naas_abi_core import logger
from naas_abi_core.integration import Integration
from naas_abi_core.integration.integration import (
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from pydantic import BaseModel, Field

GEONAMES_BASE = "https://download.geonames.org/export"

POSTAL_CODE_COLUMNS = [
    "country_code",
    "postal_code",
    "place_name",
    "admin_name1",
    "admin_code1",
    "admin_name2",
    "admin_code2",
    "admin_name3",
    "admin_code3",
    "latitude",
    "longitude",
    "accuracy",
]

COUNTRY_INFO_COLUMNS = [
    "iso",
    "iso3",
    "iso_numeric",
    "fips",
    "country",
    "capital",
    "area",
    "population",
    "continent",
    "tld",
    "currency_code",
    "currency_name",
    "phone",
    "postal_code_format",
    "postal_code_regex",
    "languages",
    "geonameid",
    "neighbours",
    "equivalent_fips_code",
]


@dataclass
class GeoNamesIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the GeoNames integration.

    Attributes:
        cache_dir: Local directory used to cache downloaded GeoNames dumps.
        timeout: HTTP timeout in seconds for downloads.
    """

    cache_dir: str = "datastore/domains/locations/geonames"
    timeout: int = 120


class GeoNamesIntegration(Integration):
    """Integration with the GeoNames open gazetteer (https://www.geonames.org).

    Downloads and caches GeoNames' postal-code and country-info dumps -- released
    under CC BY 4.0, attribution required for redistribution -- to provide
    city/region/state/country/postal_code lookups worldwide.
    """

    __configuration: GeoNamesIntegrationConfiguration

    def __init__(self, configuration: GeoNamesIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__cache_dir = Path(self.__configuration.cache_dir)

    def __download(self, url: str, dest: Path) -> Path:
        if dest.exists():
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with requests.get(
                url, stream=True, timeout=self.__configuration.timeout
            ) as response:
                response.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
        except requests.exceptions.RequestException as e:
            logger.error(f"GeoNames download failed for {url}: {e}")
            raise IntegrationConnectionError(
                f"Failed to download {url}: {str(e)}"
            ) from e
        return dest

    def get_country_info(self) -> List[dict]:
        """Get ISO country code to country name mapping.

        Returns:
            List of dicts with country_code and country.
        """
        path = self.__download(
            f"{GEONAMES_BASE}/dump/countryInfo.txt", self.__cache_dir / "countryInfo.txt"
        )
        df = pd.read_csv(
            path,
            sep="\t",
            comment="#",
            names=COUNTRY_INFO_COLUMNS,
            header=None,
            dtype=str,
            keep_default_na=False,
        )
        df = df[["iso", "country"]].rename(columns={"iso": "country_code"})
        return df.to_dict(orient="records")

    def get_postal_codes(self, country_code: Optional[str] = None) -> List[dict]:
        """Get city/region/state/postal_code records for a country, or the whole world.

        Args:
            country_code: ISO-3166 alpha-2 country code (e.g. "FR"). Omit for the
                full world dump (~250MB download, cached after the first call).

        Returns:
            List of dicts with city, region, state, country_code, postal_code,
            latitude, longitude.
        """
        filename = f"{country_code}.zip" if country_code else "allCountries.zip"
        txt_name = f"{country_code}.txt" if country_code else "allCountries.txt"
        zip_path = self.__download(
            f"{GEONAMES_BASE}/zip/{filename}", self.__cache_dir / filename
        )
        try:
            with zipfile.ZipFile(zip_path) as zf, zf.open(txt_name) as f:
                df = pd.read_csv(
                    f,
                    sep="\t",
                    names=POSTAL_CODE_COLUMNS,
                    header=None,
                    dtype=str,
                    keep_default_na=False,
                )
        except (zipfile.BadZipFile, KeyError) as e:
            raise IntegrationConnectionError(
                f"Failed to parse GeoNames postal codes for {country_code or 'world'}: {str(e)}"
            ) from e

        df = df.rename(
            columns={
                "place_name": "city",
                "admin_name1": "state",
                "admin_name2": "region",
            }
        )
        return df[
            ["city", "region", "state", "country_code", "postal_code", "latitude", "longitude"]
        ].to_dict(orient="records")

    def search_postal_code(self, country_code: str, postal_code: str) -> List[dict]:
        """Look up city/region/state for a specific postal code.

        Args:
            country_code: ISO-3166 alpha-2 country code (e.g. "FR").
            postal_code: Postal code to look up.

        Returns:
            List of matching location dicts (a postal code can map to several places).
        """
        records = self.get_postal_codes(country_code)
        return [r for r in records if r["postal_code"] == postal_code]

    @staticmethod
    def as_tools(configuration: GeoNamesIntegrationConfiguration) -> List[StructuredTool]:
        """Get tools for the GeoNames integration.

        Args:
            configuration: GeoNames integration configuration.

        Returns:
            List of tools.
        """
        integration = GeoNamesIntegration(configuration)

        class GetCountryInfoParameters(BaseModel):
            pass

        class GetPostalCodesParameters(BaseModel):
            country_code: Optional[str] = Field(
                default=None,
                description="ISO-3166 alpha-2 country code, e.g. 'FR'. Omit for the full world dump.",
            )

        class SearchPostalCodeParameters(BaseModel):
            country_code: str = Field(..., description="ISO-3166 alpha-2 country code, e.g. 'FR'.")
            postal_code: str = Field(..., description="Postal code to look up.")

        return [
            StructuredTool(
                name="get_geonames_country_info",
                description="Get the ISO country code to country name mapping from GeoNames",
                func=lambda **kwargs: integration.get_country_info(),
                args_schema=GetCountryInfoParameters,
            ),
            StructuredTool(
                name="get_geonames_postal_codes",
                description="Get city/region/state/postal_code records for a country from GeoNames",
                func=lambda **kwargs: integration.get_postal_codes(**kwargs),
                args_schema=GetPostalCodesParameters,
            ),
            StructuredTool(
                name="search_geonames_postal_code",
                description="Look up city/region/state for a specific postal code via GeoNames",
                func=lambda **kwargs: integration.search_postal_code(**kwargs),
                args_schema=SearchPostalCodeParameters,
            ),
        ]

from dataclasses import dataclass
from typing import Dict, List, Optional

from babel import Locale, UnknownLocaleError
from langchain_core.tools import StructuredTool
from naas_abi_core.integration import Integration
from naas_abi_core.integration.integration import (
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from pydantic import BaseModel, Field

DEFAULT_LOCALES = ["en", "fr", "es", "de", "pt", "zh", "ar", "ja", "ru", "hi"]


@dataclass
class CLDRIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the CLDR integration.

    Attributes:
        default_locale: Locale used when a call doesn't specify one.
    """

    default_locale: str = "en"


class CLDRIntegration(Integration):
    """Integration with the Unicode CLDR (Common Locale Data Repository), via the
    `babel` package -- bundled, offline locale data (no network access required).

    Provides localized display names for countries/territories and languages,
    complementing the English-only GeoNames/pgeocode/geonamescache data with
    multilingual names useful for matching user input in any language.
    """

    __configuration: CLDRIntegrationConfiguration

    def __init__(self, configuration: CLDRIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def __locale(self, locale: Optional[str]) -> Locale:
        try:
            return Locale.parse(locale or self.__configuration.default_locale)
        except UnknownLocaleError as e:
            raise IntegrationConnectionError(f"Unknown CLDR locale {locale!r}: {str(e)}") from e

    def get_territory_name(self, territory_code: str, locale: Optional[str] = None) -> Optional[str]:
        """Get the localized display name of a country/territory code.

        Args:
            territory_code: ISO-3166 alpha-2 (or UN M49) territory code, e.g. "FR".
            locale: CLDR locale code, e.g. "fr", "ja". Defaults to `default_locale`.

        Returns:
            Localized territory name, or None if the code is not a known territory.
        """
        return self.__locale(locale).territories.get(territory_code.upper())

    def get_territory_names(self, territory_code: str, locales: Optional[List[str]] = None) -> Dict[str, str]:
        """Get the localized display name of a territory across multiple locales.

        Args:
            territory_code: ISO-3166 alpha-2 (or UN M49) territory code, e.g. "FR".
            locales: CLDR locale codes to translate into. Defaults to a curated
                set of major world languages.

        Returns:
            Dict mapping locale code to localized territory name (locales with
            no known name for this territory are omitted).
        """
        names = {}
        for loc in locales or DEFAULT_LOCALES:
            name = self.get_territory_name(territory_code, loc)
            if name is not None:
                names[loc] = name
        return names

    def get_territories(self, locale: Optional[str] = None) -> List[dict]:
        """Get every CLDR territory code and its localized display name.

        Args:
            locale: CLDR locale code, e.g. "fr". Defaults to `default_locale`.

        Returns:
            List of dicts with `territory_code` and `name`.
        """
        territories = self.__locale(locale).territories
        return [{"territory_code": code, "name": name} for code, name in territories.items()]

    def get_language_name(self, language_code: str, locale: Optional[str] = None) -> Optional[str]:
        """Get the localized display name of a language code.

        Args:
            language_code: ISO-639 language code, e.g. "en", "ja".
            locale: CLDR locale to display the language name in. Defaults to `default_locale`.

        Returns:
            Localized language name, or None if the code is not known.
        """
        return self.__locale(locale).languages.get(language_code.lower())

    @staticmethod
    def as_tools(configuration: CLDRIntegrationConfiguration) -> List[StructuredTool]:
        """Get tools for the CLDR integration.

        Args:
            configuration: CLDR integration configuration.

        Returns:
            List of tools.
        """
        integration = CLDRIntegration(configuration)

        class GetTerritoryNameParameters(BaseModel):
            territory_code: str = Field(..., description="ISO-3166 alpha-2 territory code, e.g. 'FR'.")
            locale: Optional[str] = Field(
                default=None, description="CLDR locale code, e.g. 'fr', 'ja'. Defaults to English."
            )

        class GetTerritoryNamesParameters(BaseModel):
            territory_code: str = Field(..., description="ISO-3166 alpha-2 territory code, e.g. 'FR'.")
            locales: Optional[List[str]] = Field(
                default=None,
                description="CLDR locale codes to translate into. Defaults to a curated set of major world languages.",
            )

        class GetTerritoriesParameters(BaseModel):
            locale: Optional[str] = Field(
                default=None, description="CLDR locale code, e.g. 'fr'. Defaults to English."
            )

        class GetLanguageNameParameters(BaseModel):
            language_code: str = Field(..., description="ISO-639 language code, e.g. 'en', 'ja'.")
            locale: Optional[str] = Field(
                default=None, description="CLDR locale to display the language name in. Defaults to English."
            )

        return [
            StructuredTool(
                name="get_cldr_territory_name",
                description="Get the localized display name of a country/territory code via CLDR",
                func=lambda **kwargs: integration.get_territory_name(**kwargs),
                args_schema=GetTerritoryNameParameters,
            ),
            StructuredTool(
                name="get_cldr_territory_names",
                description="Get the localized display name of a territory across multiple locales via CLDR",
                func=lambda **kwargs: integration.get_territory_names(**kwargs),
                args_schema=GetTerritoryNamesParameters,
            ),
            StructuredTool(
                name="get_cldr_territories",
                description="Get every CLDR territory code and its localized display name",
                func=lambda **kwargs: integration.get_territories(**kwargs),
                args_schema=GetTerritoriesParameters,
            ),
            StructuredTool(
                name="get_cldr_language_name",
                description="Get the localized display name of a language code via CLDR",
                func=lambda **kwargs: integration.get_language_name(**kwargs),
                args_schema=GetLanguageNameParameters,
            ),
        ]

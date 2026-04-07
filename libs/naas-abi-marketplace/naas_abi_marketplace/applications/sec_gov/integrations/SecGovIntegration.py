import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import requests
from langchain_core.tools import BaseTool
from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.StorageUtils import StorageUtils

cache = CacheFactory.CacheFS_find_storage(subpath="sec_gov")


@dataclass
class SecGovIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for U.S. SEC public data integration.

    Attributes:
        object_storage: Backing store for downloaded SEC files.
        datastore_path: Object storage prefix for SEC artifacts.
        company_tickers_url: Source URL for the company tickers JSON feed.
        user_agent: SEC EDGAR requires a descriptive User-Agent header.
    """

    object_storage: ObjectStorageService
    user_agent: str
    datastore_path: str = "sec_gov"


class SecGovIntegration(Integration):
    """Fetches public SEC data files and persists them to object storage."""

    __configuration: SecGovIntegrationConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: SecGovIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)

    def make_request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        timeout: int = 120,
        **kwargs: Any,
    ) -> requests.Response:
        default_headers = {
            "User-Agent": self.__configuration.user_agent,
            "Accept": "application/json",
        }
        merged_headers = {**default_headers, **(headers or {})}
        try:
            response = requests.request(
                method,
                url,
                headers=merged_headers,
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(
                f"SEC request failed ({url}): {e!s}"
            ) from e

    @staticmethod
    def _normalize_cik(cik: str | int) -> str:
        cik_str = str(cik).strip()
        if cik_str.startswith("CIK"):
            cik_str = cik_str[3:]
        cik_digits = "".join(ch for ch in cik_str if ch.isdigit())
        return cik_digits.zfill(10)

    @cache(
        lambda self: "get_company_tickers",
        DataType.JSON,
        ttl=timedelta(days=7),
    )
    def get_company_tickers(self, save_result: bool = False) -> dict[str, Any]:
        """Download SEC company_tickers.json and return parsed payload."""
        response = self.make_request("https://www.sec.gov/files/company_tickers.json")

        output_dir = os.path.join(
            self.__configuration.datastore_path, "files", "company_tickers"
        )
        result = response.json()
        if save_result:
            self.__storage_utils.save_json(result, output_dir, "company_tickers.json")
        return result

    @cache(
        lambda self: "get_company_tickers_exchange",
        DataType.JSON,
        ttl=timedelta(days=7),
    )
    def get_company_tickers_exchange(self, save_result: bool = False) -> dict[str, Any]:
        """Download SEC company_tickers_exchange.json and return parsed payload."""
        response = self.make_request(
            "https://www.sec.gov/files/company_tickers_exchange.json"
        )

        output_dir = os.path.join(
            self.__configuration.datastore_path, "files", "company_tickers_exchange"
        )
        result = response.json()
        if save_result:
            self.__storage_utils.save_json(
                result, output_dir, "company_tickers_exchange.json"
            )
        return result

    @cache(
        lambda self: "get_company_tickers_mf",
        DataType.JSON,
        ttl=timedelta(days=7),
    )
    def get_company_tickers_mf(self, save_result: bool = False) -> dict[str, Any]:
        """Download SEC company_tickers_mf.json and return parsed payload."""
        response = self.make_request(
            "https://www.sec.gov/files/company_tickers_mf.json"
        )

        output_dir = os.path.join(
            self.__configuration.datastore_path, "files", "company_tickers_mf"
        )
        result = response.json()
        if save_result:
            self.__storage_utils.save_json(
                result, output_dir, "company_tickers_mf.json"
            )
        return result

    @cache(
        lambda self, cik: f"get_submissions_{SecGovIntegration._normalize_cik(cik)}",
        DataType.JSON,
        ttl=timedelta(days=7),
    )
    def get_submissions(
        self, cik: str | int, save_result: bool = False
    ) -> dict[str, Any]:
        """Fetch SEC submissions JSON for a given CIK (zero-padded to 10 digits)."""
        cik_10 = self._normalize_cik(cik)
        url = f"https://data.sec.gov/submissions/CIK{cik_10}.json"
        response = self.make_request(url)

        output_dir = os.path.join(self.__configuration.datastore_path, "submissions")
        result = response.json()
        if save_result:
            self.__storage_utils.save_json(result, output_dir, f"CIK{cik_10}.json")
        return result


def as_tools(configuration: SecGovIntegrationConfiguration) -> list[BaseTool]:
    return []

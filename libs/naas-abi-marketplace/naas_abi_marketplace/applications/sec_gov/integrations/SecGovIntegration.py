import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import requests
from langchain_core.tools import BaseTool, StructuredTool
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
from pydantic import BaseModel

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

    @cache(
        lambda self: "get_company_tickers",
        DataType.JSON,
        ttl=timedelta(days=7),
    )
    def get_company_tickers(self) -> dict[str, Any]:
        """Download SEC company_tickers.json, store raw bytes, return parsed payload."""
        headers = {
            "User-Agent": self.__configuration.user_agent,
            "Accept": "application/json",
        }
        try:
            response = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(
                f"SEC company tickers request failed: {e!s}"
            ) from e

        output_dir = os.path.join(
            self.__configuration.datastore_path, "files", "company_tickers"
        )
        result = response.json()
        self.__storage_utils.save_json(
            response.json(), output_dir, "company_tickers.json"
        )
        return result


def as_tools(configuration: SecGovIntegrationConfiguration) -> list[BaseTool]:
    """Expose SEC.gov integration as LangChain tools."""
    integration = SecGovIntegration(configuration)

    class GetCompanyTickersSchema(BaseModel):
        pass

    return [
        StructuredTool(
            name="sec_get_company_tickers",
            description=(
                "Download the SEC official company tickers mapping (CIK, ticker, name) "
                "from https://www.sec.gov/files/company_tickers.json, store the raw JSON "
                "in object storage, and return the parsed dataset with storage location "
                "and record_count."
            ),
            func=lambda **_kw: integration.get_company_tickers(),
            args_schema=GetCompanyTickersSchema,
        ),
    ]

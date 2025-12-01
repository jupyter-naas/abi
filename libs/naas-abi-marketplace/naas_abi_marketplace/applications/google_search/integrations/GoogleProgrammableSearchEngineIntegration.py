import datetime
import os
import re
from dataclasses import dataclass
from typing import List, Optional

import requests
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core import logger
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_marketplace.applications.google_search import ABIModule

cache = CacheFactory.CacheFS_find_storage(subpath="google_search")


@dataclass
class GoogleProgrammableSearchEngineIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for GoogleProgrammableSearchEngine.

    Attributes:
        api_key (str): Google API key
        search_engine_id (str): Google Search Engine ID
        base_url (str): Google Programmable Search Engine base URL
        data_store_path (str): Path to the datastore
    """

    api_key: str
    search_engine_id: str
    base_url: str = "https://www.googleapis.com/customsearch/v1"
    datastore_path: str = ABIModule.get_instance().configuration.datastore_path


class GoogleProgrammableSearchEngineIntegration(Integration):
    """GoogleProgrammableSearchEngine integration for performing Google searches.

    This class provides methods to search Google Programmable Search Engine and get list of urls from search results.
    """

    __configuration: GoogleProgrammableSearchEngineIntegrationConfiguration
    __storage_utils: StorageUtils

    def __init__(
        self, configuration: GoogleProgrammableSearchEngineIntegrationConfiguration
    ):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

    @cache(
        lambda self, query, num_results: f"googlesearch_search_{query}_{num_results}",
        cache_type=DataType.JSON,
        ttl=datetime.timedelta(days=1),
    )
    def query(self, query: str, num_results: int = 5) -> List[dict]:
        """
        Perform a Google Custom Search using requests, with automatic pagination.
        Returns a list of dicts with title, link, snippet.
        """
        items: list = []
        url = (
            self.__configuration.base_url
        )  # Should be "https://www.googleapis.com/customsearch/v1"

        def clean_string(string: str) -> str:
            # Remove special characters except spaces and pipes
            cleaned = re.sub(r"[^\w\s|]", "", string)
            cleaned = cleaned.strip()
            cleaned = cleaned.replace(" ", "_")
            return cleaned

        # Google Custom Search API: max 10 results per request
        remaining = num_results
        start_index = 1  # API uses 1-based indexing for start

        while remaining > 0:
            fetch_count = min(10, remaining)
            params: dict = {
                "key": self.__configuration.api_key,
                "cx": self.__configuration.search_engine_id,
                "q": query,
                "num": fetch_count,
                "start": start_index,
            }

            response = requests.get(url, params=params)
            if response.status_code != 200:
                logger.error(f"Error: {response.status_code} {response.text}")
                break

            data = response.json()
            items = data.get("items", [])
            remaining -= len(items)
            start_index += len(items)
            if len(items) < fetch_count:
                break  # Reached the last page

        query_clean = clean_string(query)
        self.__storage_utils.save_json(
            items,
            os.path.join(self.__configuration.datastore_path, "queries", query_clean),
            query_clean + ".json",
        )
        return items


def as_tools(configuration: GoogleProgrammableSearchEngineIntegrationConfiguration):
    """Convert GoogleProgrammableSearchEngine integration into LangChain tools."""
    from typing import Annotated

    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GoogleProgrammableSearchEngineIntegration(configuration)

    class SearchSchema(BaseModel):
        query: Annotated[str, Field(..., description="Search query")]
        num_results: Optional[
            Annotated[int, Field(5, description="Number of results to return")]
        ]

    return [
        StructuredTool(
            name="googlesearch_query",
            description="Search the web using Google Programmable Search Engine",
            func=lambda **kwargs: integration.query(**kwargs),
            args_schema=SearchSchema,
        ),
    ]

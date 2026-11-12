import datetime
import os
import re
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from naas_abi_core import logger
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.utils import outbound
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.applications.google_search import ABIModule

cache = CacheFactory.CacheFS_find_storage(subpath="google_search")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
_MAX_PAGE_BYTES = 5 * 1024 * 1024
_FETCH_TIMEOUT_SECONDS = 30.0


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
    datastore_path: str = field(default_factory=lambda: ABIModule.get_instance().configuration.datastore_path)


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
    def query(self, query: str, num_results: int = 5) -> list[dict]:
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

    def extract_content(self, url: str) -> str:
        """
        Fetch a public URL and extract text content from HTML.

        The page is fetched through the guarded outbound client (public
        addresses only, every redirect checked, size and time capped), and its
        text is returned to the caller only: it is not cached or stored.

        Args:
            url (str): The URL to fetch and extract content from

        Returns:
            str: Extracted text content from the HTML page

        Raises:
            outbound.OutboundRefused: If the URL does not lead to a public address
            outbound.OutboundError: If the page could not be fetched
        """
        response = outbound.fetch(
            url,
            headers={"User-Agent": _USER_AGENT},
            max_bytes=_MAX_PAGE_BYTES,
            timeout=_FETCH_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise outbound.OutboundError(f"HTTP {response.status_code}")

        soup = BeautifulSoup(response.text(), "html.parser")
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        text = soup.get_text(separator=" ", strip=True)

        # Clean up excessive whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return " ".join(chunk for chunk in chunks if chunk)


def as_tools(configuration: GoogleProgrammableSearchEngineIntegrationConfiguration):
    """Convert GoogleProgrammableSearchEngine integration into LangChain tools."""
    from typing import Annotated

    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GoogleProgrammableSearchEngineIntegration(configuration)

    class SearchSchema(BaseModel):
        query: Annotated[str, Field(..., description="Search query")]
        num_results: Annotated[int, Field(description="Number of results to return")] | None = 5

    class ExtractContentSchema(BaseModel):
        url: Annotated[str, Field(..., description="URL to extract content from")]

    return [
        StructuredTool(
            name="googlesearch_query",
            description="Search the web using Google Programmable Search Engine",
            func=lambda **kwargs: integration.query(**kwargs),
            args_schema=SearchSchema,
        ),
        StructuredTool(
            name="googlesearch_extract_content_from_url",
            description="Extract text content from a web page URL using BeautifulSoup",
            func=lambda **kwargs: integration.extract_content(**kwargs),
            args_schema=ExtractContentSchema,
        ),
    ]

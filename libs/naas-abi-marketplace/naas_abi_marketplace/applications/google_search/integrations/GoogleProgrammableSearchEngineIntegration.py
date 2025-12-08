import datetime
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from naas_abi_core import logger
from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.utils.StorageUtils import StorageUtils
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

    @cache(
        lambda self, url: f"googlesearch_extract_{url}",
        cache_type=DataType.TEXT,
        ttl=datetime.timedelta(days=1),
    )
    def extract_content(self, url: str) -> str:
        """
        Fetch a URL and extract text content from HTML.
        
        Args:
            url (str): The URL to fetch and extract content from
            
        Returns:
            str: Extracted text content from the HTML page
            
        Raises:
            requests.RequestException: If the HTTP request fails
            Exception: If HTML parsing fails
        """
        try:
            # Fetch the URL with a user agent to avoid blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            # Extract text content
            text = soup.get_text(separator=" ", strip=True)
            
            # Clean up excessive whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)
            
            # Save to storage
            def clean_string(string: str) -> str:
                # Remove special characters except spaces and pipes
                cleaned = re.sub(r"[^\w\s|]", "", string)
                cleaned = cleaned.strip()
                cleaned = cleaned.replace(" ", "_")
                return cleaned
            
            url_clean = clean_string(url)
            self.__storage_utils.save_text(
                text,
                os.path.join(self.__configuration.datastore_path, "extracted_content", url_clean),
                url_clean + ".txt",
            )
            
            return text
            
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            raise


def as_tools(configuration: GoogleProgrammableSearchEngineIntegrationConfiguration):
    """Convert GoogleProgrammableSearchEngine integration into LangChain tools."""
    from typing import Annotated

    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GoogleProgrammableSearchEngineIntegration(configuration)

    class SearchSchema(BaseModel):
        query: Annotated[str, Field(..., description="Search query")]
        num_results: Optional[Annotated[
            int, 
            Field(description="Number of results to return")]
        ] = 5

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

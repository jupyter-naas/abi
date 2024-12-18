from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from datetime import datetime

LOGO_URL = "https://logo.clearbit.com/newsapi.org"

@dataclass
class NewsAPIIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for NewsAPI integration.
    
    Attributes:
        api_key (str): NewsAPI key
        base_url (str): Base URL for NewsAPI. Defaults to "https://newsapi.org/v2"
    """
    api_key: str
    base_url: str = "https://newsapi.org/v2"

class NewsAPIIntegration(Integration):
    """NewsAPI integration client.
    
    This integration provides methods to interact with NewsAPI endpoints
    for retrieving news articles and headlines.
    """

    __configuration: NewsAPIIntegrationConfiguration

    def __init__(self, configuration: NewsAPIIntegrationConfiguration):
        """Initialize NewsAPI client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "X-Api-Key": self.__configuration.api_key
        }

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make HTTP request to NewsAPI.
        
        Args:
            endpoint (str): API endpoint
            params (Dict, optional): Query parameters. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"NewsAPI request failed: {str(e)}")

    def get_top_headlines(self,
                         country: Optional[str] = None,
                         category: Optional[str] = None,
                         q: Optional[str] = None,
                         page_size: int = 20,
                         page: int = 1) -> Dict:
        """Get top headlines.
        
        Args:
            country (str, optional): 2-letter ISO 3166-1 country code
            category (str, optional): Category of news
            q (str, optional): Keywords or phrases to search for
            page_size (int, optional): Number of results per page (max 100)
            page (int, optional): Page number
            
        Returns:
            Dict: Top headlines data
        """
        params = {
            "pageSize": page_size,
            "page": page
        }
        if country:
            params["country"] = country
        if category:
            params["category"] = category
        if q:
            params["q"] = q
            
        return self._make_request("/top-headlines", params)

    def get_everything(self,
                      q: str,
                      from_date: Optional[str] = None,
                      to_date: Optional[str] = None,
                      language: str = "en",
                      sort_by: str = "publishedAt",
                      page_size: int = 20,
                      page: int = 1) -> Dict:
        """Search all articles.
        
        Args:
            q (str): Keywords or phrases to search for
            from_date (str, optional): Start date in YYYY-MM-DD format
            to_date (str, optional): End date in YYYY-MM-DD format
            language (str, optional): 2-letter ISO-639-1 language code
            sort_by (str, optional): Sort articles by (relevancy, popularity, publishedAt)
            page_size (int, optional): Number of results per page (max 100)
            page (int, optional): Page number
            
        Returns:
            Dict: Search results
        """
        params = {
            "q": q,
            "language": language,
            "sortBy": sort_by,
            "pageSize": page_size,
            "page": page
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
            
        return self._make_request("/everything", params)

def as_tools(configuration: NewsAPIIntegrationConfiguration):
    """Convert NewsAPI integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = NewsAPIIntegration(configuration)
    
    class TopHeadlinesSchema(BaseModel):
        country: Optional[str] = Field(None, description="2-letter ISO 3166-1 country code")
        category: Optional[str] = Field(None, description="Category of news")
        q: Optional[str] = Field(None, description="Keywords or phrases to search for")
        page_size: int = Field(default=20, description="Number of results per page (max 100)")
        page: int = Field(default=1, description="Page number")

    class EverythingSchema(BaseModel):
        q: str = Field(..., description="Keywords or phrases to search for")
        from_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format")
        to_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format")
        language: str = Field(default="en", description="2-letter ISO-639-1 language code")
        sort_by: str = Field(default="publishedAt", description="Sort articles by (relevancy, popularity, publishedAt)")
        page_size: int = Field(default=20, description="Number of results per page (max 100)")
        page: int = Field(default=1, description="Page number")
    
    return [
        StructuredTool(
            name="get_news_top_headlines",
            description="Get top news headlines with optional filters",
            func=lambda country, category, q, page_size, page: integration.get_top_headlines(
                country, category, q, page_size, page
            ),
            args_schema=TopHeadlinesSchema
        ),
        StructuredTool(
            name="search_news_articles",
            description="Search all news articles with various filters",
            func=lambda q, from_date, to_date, language, sort_by, page_size, page: integration.get_everything(
                q, from_date, to_date, language, sort_by, page_size, page
            ),
            args_schema=EverythingSchema
        )
    ]
from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests

@dataclass
class SerperIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Serper.dev integration.
    
    Attributes:
        api_key (str): Serper API key
        base_url (str): Base URL for Serper API. Defaults to "https://google.serper.dev"
    """
    api_key: str
    base_url: str = "https://google.serper.dev"

class SerperIntegration(Integration):
    """Serper.dev API integration client.
    
    This class provides methods to interact with Serper's API endpoints
    for Google search results.
    """

    __configuration: SerperIntegrationConfiguration

    def __init__(self, configuration: SerperIntegrationConfiguration):
        """Initialize Serper client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "X-API-KEY": self.__configuration.api_key,
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, json: Dict) -> Dict:
        """Make HTTP request to Serper API.
        
        Args:
            endpoint (str): API endpoint
            json (Dict): JSON body for request
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=json
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Serper API request failed: {str(e)}")

    def search(self,
              q: str,
              num: int = 10,
              search_type: str = "search",
              gl: str = "us",
              hl: str = "en") -> Dict:
        """Perform a Google search.
        
        Args:
            q (str): Search query
            num (int, optional): Number of results. Defaults to 10.
            search_type (str, optional): Type of search (search, images, news, places)
            gl (str, optional): Country of search. Defaults to "us".
            hl (str, optional): Language of search. Defaults to "en".
            
        Returns:
            Dict: Search results
        """
        payload = {
            "q": q,
            "num": num,
            "gl": gl,
            "hl": hl
        }
        
        return self._make_request(f"/search", payload)

    def news_search(self,
                   q: str,
                   num: int = 10,
                   gl: str = "us",
                   hl: str = "en") -> Dict:
        """Perform a Google News search.
        
        Args:
            q (str): Search query
            num (int, optional): Number of results. Defaults to 10.
            gl (str, optional): Country of search. Defaults to "us".
            hl (str, optional): Language of search. Defaults to "en".
            
        Returns:
            Dict: News search results
        """
        payload = {
            "q": q,
            "num": num,
            "gl": gl,
            "hl": hl,
            "type": "news"
        }
        
        return self._make_request(f"/search", payload)

    def image_search(self,
                    q: str,
                    num: int = 10,
                    gl: str = "us",
                    hl: str = "en") -> Dict:
        """Perform a Google Image search.
        
        Args:
            q (str): Search query
            num (int, optional): Number of results. Defaults to 10.
            gl (str, optional): Country of search. Defaults to "us".
            hl (str, optional): Language of search. Defaults to "en".
            
        Returns:
            Dict: Image search results
        """
        payload = {
            "q": q,
            "num": num,
            "gl": gl,
            "hl": hl,
            "type": "images"
        }
        
        return self._make_request(f"/search", payload)

def as_tools(configuration: SerperIntegrationConfiguration):
    """Convert Serper integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = SerperIntegration(configuration)
    
    class SearchSchema(BaseModel):
        q: str = Field(..., description="Search query")
        num: int = Field(default=10, description="Number of results")
        gl: str = Field(default="us", description="Country of search")
        hl: str = Field(default="en", description="Language of search")
    
    return [
        StructuredTool(
            name="google_search",
            description="Perform a Google search using Serper.dev",
            func=lambda q, num, gl, hl: integration.search(q, num, "search", gl, hl),
            args_schema=SearchSchema
        ),
        StructuredTool(
            name="google_news_search",
            description="Perform a Google News search using Serper.dev",
            func=lambda q, num, gl, hl: integration.news_search(q, num, gl, hl),
            args_schema=SearchSchema
        ),
        StructuredTool(
            name="google_image_search",
            description="Perform a Google Image search using Serper.dev",
            func=lambda q, num, gl, hl: integration.image_search(q, num, gl, hl),
            args_schema=SearchSchema
        )
    ] 
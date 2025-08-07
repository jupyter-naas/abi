from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from abi import logger
from typing import Any
from pydantic import BaseModel
import requests
from abi.services.cache.CacheFactory import CacheFactory
# from abi.services.cache.CachePort import DataType

cache = CacheFactory.CacheFS_find_storage(subpath="openai_web_search")

@dataclass
class OpenAIWebSearchIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenAIWebSearch workflow.
    
    Attributes:
        api_key (str): OpenAI API key
        model (str): OpenAI model
    """
    api_key: str
    model : str = "gpt-4o"

class OpenAIWebSearchIntegration(Integration):
    """Workflow for performing web searches using OpenAI."""
    
    __configuration: OpenAIWebSearchIntegrationConfiguration
    
    def __init__(self, configuration: OpenAIWebSearchIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    # @cache(lambda self, query, search_context_size: f"openai_web_search_{query}_{search_context_size}", cache_type=DataType.JSON)
    def search_web(self, query: str, search_context_size: str = "medium") -> Any:
        """Execute the web search workflow.
        
        Args:
            parameters (OpenAIWebSearchParameters): Search parameters
            
        Returns:
            str: Search results from OpenAI
        """        
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.__configuration.api_key}"
                },
                json={
                    "model": self.__configuration.model,
                    "tools": [{
                        "type": "web_search_preview",
                        "search_context_size": search_context_size
                        }],    
                    "input": query
                }
            )
            response_json = response.json()
            output = response_json.get("output")
            return output
        except Exception as e:
            logger.error(f"Error executing OpenAI web search: {str(e)}")
            return str(e)
        
def as_tools(configuration: OpenAIWebSearchIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    integration = OpenAIWebSearchIntegration(configuration)

    class SearchWebSchema(BaseModel):
        query: str = Field(..., description="The query to search the web")
        search_context_size : str = Field("medium", description="The search context size")

    return [
        StructuredTool(
            name="openai_web_search",
            description="Search the web using OpenAI.",
            func=lambda **kwargs: integration.search_web(**kwargs),
            args_schema=SearchWebSchema
        )
    ]

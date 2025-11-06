from typing import Optional, Dict, List
import requests
from dataclasses import dataclass
from abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from abi.services.cache.CacheFactory import CacheFactory
from abi.services.cache.CachePort import DataType
from src.utils.Storage import save_json
import datetime
import os


cache = CacheFactory.CacheFS_find_storage(subpath="openrouter")


@dataclass
class OpenRouterAPIIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OpenRouter API Integration.
    
    Attributes:
        api_key (str): OpenRouter API key for authentication
        base_url (str): Base URL for OpenRouter API
        datastore_path (str): Path to the datastore
    """
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    datastore_path: str = "datastore/openrouter"


class OpenRouterAPIIntegration(Integration):
    """OpenRouter API Integration class for interacting with OpenRouter API.
    
    This class provides methods to interact with OpenRouter's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (OpenRouterAPIIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = OpenRouterAPIIntegrationConfiguration(
        ...     api_key="your_api_key"
        ... )
        >>> integration = OpenRouterAPIIntegration(config)
    """

    __configuration: OpenRouterAPIIntegrationConfiguration

    def __init__(self, configuration: OpenRouterAPIIntegrationConfiguration):
        """Initialize OpenRouter API client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }

    @cache(lambda self, method, endpoint, data, params: method + "_" + endpoint + ("_".join(f"{k}_{v}" for k,v in params.items()) if params else ""), cache_type=DataType.JSON, ttl=datetime.timedelta(days=7))
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None, 
        params: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to OpenRouter API endpoint.
        
        Args:
            method (str): HTTP method to use (GET, POST, PATCH, DELETE).
            endpoint (str): The API endpoint to request.
            data (dict, optional): JSON body for the request.
            params (dict, optional): Query parameters for the request.
        
        Returns:
            dict: Response data from the API.
            
        Raises:
            IntegrationConnectionError: If the request fails.
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"OpenRouter API request failed: {str(e)}")
    
    # Beta Responses
    def create_response(
        self, 
        input_prompt: str, 
        tools: Optional[list[Dict]] = None, 
        model: str = "openai/gpt-4.1-mini", 
        temperature: float = 0.7, 
        top_p: float = 0.9
    ) -> Dict:
        """Create a response.
            
        Args:
            input_prompt (str): The input prompt to use for the response.
            tools (List[Dict]): The tools to use for the response. Example: 
            [
                {
                    "type": "function", 
                    "name": "get_current_weather", 
                    "description": "Get the current weather in a given location", 
                    "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}
                }
            ]
            model (str): The model to use for the response.
            temperature (float): The temperature to use for the response.
            top_p (float): The top_p to use for the response.
            
        Returns:
            dict: Response data from the API.
        """
        payload = {
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": input_prompt
                }
            ],
            "tools": tools,
            "model": model,
            "temperature": temperature,
            "top_p": top_p
        }
        return self._make_request("POST", "/responses", data=payload)
    
    # Analytics
    def get_user_activity(self, date: Optional[str] = None) -> Dict:
        """Get user activity grouped by endpoint.
        
        Args:
            date (str): Filter by a single UTC date in the last 30 days (YYYY-MM-DD format).
            
        Returns:
            dict: User activity data grouped by endpoint.
        """
        return self._make_request("GET", "/activity", params={"date": date})
    
    # Credits
    def get_remaining_credits(self) -> Dict:
        """Get remaining credits.
        
        Returns:
            dict: Information about remaining credits.
        """
        return self._make_request("GET", "/credits")
    
    # Models
    def get_total_models_count(self) -> Dict:
        """Get total count of available models.
        
        Returns:
            dict: Total count of available models.
        """
        return self._make_request("GET", "/models/count")
    
    def list_all_models(self, params: Optional[Dict] = None) -> List:
        """
        List all models and their properties, along with splits by provider (owner).

        Args:
            params (dict, optional): Query parameters for filtering models.

        Returns:
            dict: {
                "all": [ ...models... ],  # Flat list of all models (not wrapped in a "data" key)
                "by_provider": { "provider1": [ ...models... ], ... }
            }
        """
        response = self._make_request("GET", "/models", params=params)
        models = response.get("data", []) if isinstance(response, dict) else []
        save_json(models, os.path.join(self.__configuration.datastore_path, "models", "_all"), "models.json")

        owners: dict = {}

        for model in models:
            model_id = model.get("id", "")
            # Only split once: e.g. "openai/gpt-4" -> "openai", "gpt-4"
            owner = model_id.split("/")[0] if "/" in model_id else "unknown"
            if owner not in owners:
                owners[owner] = []
            owners[owner].append(model)

        for owner, owner_models in owners.items():
            save_json(owner_models, os.path.join(self.__configuration.datastore_path, "models", owner), "models.json")

        return models
    
    # Parameters
    def get_model_parameters(self, author: str, slug: str) -> Dict:
        """Get a model's supported parameters and data about which are most popular.
        
        Args:
            author (str): The author of the model.
            slug (str): The slug of the model.
            
        Returns:
            dict: Model parameters and popularity data.
        """
        return self._make_request("GET", "/parameters", params={"author": author, "slug": slug})
    
    # Providers
    def list_providers(self) -> Dict:
        """List all providers.
        
        Returns:
            dict: List of all providers with their information.
        """
        return self._make_request("GET", "/providers")
    
    # API Keys
    def list_api_keys(self) -> Dict:
        """List API keys.
        
        Returns:
            dict: List of all API keys.
        """
        return self._make_request("GET", "/keys")
    
    def get_current_api_key(self) -> Dict:
        """Get current API key.
        
        Returns:
            dict: Current API key information.
        """
        return self._make_request("GET", "/key")


def as_tools(configuration: OpenRouterAPIIntegrationConfiguration):
    """Convert OpenRouterAPIIntegration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel
    
    integration = OpenRouterAPIIntegration(configuration)

    class EmptySchema(BaseModel):
        pass

    return [
        StructuredTool(
            name="openrouter_list_models",
            description="List all available models from OpenRouter",
            func=lambda: integration.list_all_models(),
            args_schema=EmptySchema
        ),
        StructuredTool(
            name="openrouter_list_providers",
            description="List all providers from OpenRouter",
            func=lambda: integration.list_providers(),
            args_schema=EmptySchema
        ),
    ]
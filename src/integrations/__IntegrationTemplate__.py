from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Dict

@dataclass
class YourIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for YourIntegration.
    
    Attributes:
        attribute_1 (str): Description of attribute_1
        attribute_2 (int): Description of attribute_2
    """
    attribute_1: str
    attribute_2: int

class YourIntegration(Integration):
    """YourIntegration class for interacting with YourService.
    
    This class provides methods to interact with YourService's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (YourIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = YourIntegrationConfiguration(
        ...     attribute_1="value1",
        ...     attribute_2=42
        ... )
        >>> integration = YourIntegration(config)
    """

    __configuration: YourIntegrationConfiguration

    def __init__(self, configuration: YourIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, json: Dict = None) -> Dict:
        """Make HTTP request to YourService's API endpoint.
        
        Args:
            endpoint (str): The API endpoint to request.
            method (str): HTTP method to use (default: "GET").
            params (Dict): Query parameters for the request.
            json (Dict): JSON body for the request.
        
        Returns:
            Dict: Response data from the API.
        """
        url = f"{self.__configuration.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }
        response = requests.request(method, url, headers=headers, params=params, json=json)
        return response.json()
    
    def function_name(self, parameter: str) -> str:
        """Function description."""
        return self._make_request(f"/{parameter}")
    
def as_tools(configuration: YourIntegrationConfiguration):
    """Convert Airtable integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = YourIntegration(configuration)

    class YourToolSchema(BaseModel):
        parameter: str = Field(..., description="Description of parameter")

    return [
        StructuredTool(
        name="your_tool",
            description="Description of the tool",
            func=integration.function_name,
            args_schema=YourToolSchema
        )
    ]
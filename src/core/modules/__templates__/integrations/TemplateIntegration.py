from abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass

@dataclass
class YourIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for YourIntegration.
    
    Attributes:
        datastore_path (str): Path to the datastore
    """
    datastore_path: str = "datastore/__templates__"

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
        
    # Add methods to interact with the external service
    def _make_request(self, endpoint: str, method: str = "GET", params: dict = {}, json: dict = {}) -> dict:
        """Make HTTP request to YourService's API endpoint.
        
        Args:
            endpoint (str): The API endpoint to request.
            method (str): HTTP method to use (default: "GET").
            params (dict): Query parameters for the request.
            json (dict): JSON body for the request.
        
        Returns:
            dict: Response data from the API.
        """
        # Implementation details...
        return {}
    
    def example_method(self, parameter: str) -> dict:
        """Example method description.
        
        Args:
            parameter (str): Description of parameter.
            
        Returns:
            dict: Description of return value.
            
        Example:
            >>> integration = YourIntegration(config)
            >>> result = integration.example_method("example")
        """
        return self._make_request(f"/endpoint/{parameter}")
    
def as_tools(configuration: YourIntegrationConfiguration):
    """Convert YourIntegration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = YourIntegration(configuration)

    class ExampleToolSchema(BaseModel):
        parameter: str = Field(..., description="Description of parameter")

    return [
        StructuredTool(
            name="your_example_tool",
            description="Description of what this tool does",
            func=integration.example_method,
            args_schema=ExampleToolSchema
        )
    ]
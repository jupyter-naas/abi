from pydantic import BaseModel, Field, SecretStr
from typing import Optional, List, Dict, Any
from langchain_core.tools import StructuredTool

class UexampleIntegrationConfiguration(BaseModel):
    """Configuration for the Uexample Integration."""
    api_key: SecretStr = Field(..., description="API key for the service")
    base_url: str = Field("https://api.example.com", description="Base URL for API calls")

class UexampleSearchParameters(BaseModel):
    """Parameters for searching."""
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum number of results")

class UexampleIntegration:
    """Integration with the Uexample service."""
    
    def __init__(self, configuration: UexampleIntegrationConfiguration):
        self.__configuration = configuration
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this integration."""
        return [
            StructuredTool(
                name="search_example",
                description="Search for information in the Uexample service",
                func=self.search,
                args_schema=UexampleSearchParameters
            )
        ]
    
    def search(self, parameters: UexampleSearchParameters) -> List[Dict[str, Any]]:
        """Search for information in the Uexample service."""
        # This is a placeholder implementation
        # In a real integration, you would make API calls to the service
        
        # Example placeholder implementation
        results = [
            {"id": "result1", "title": "Sample Result 1", "description": f"This is a sample result for '{parameters.query}'"},
            {"id": "result2", "title": "Sample Result 2", "description": f"Another sample result for '{parameters.query}'"}
        ]
        
        # Return limited results
        return results[:parameters.limit]

# For testing purposes
if __name__ == "__main__":
    config = UexampleIntegrationConfiguration(
        api_key=SecretStr("your-api-key-here")
    )
    integration = UexampleIntegration(config)
    results = integration.search(UexampleSearchParameters(query="test"))
    print(results)


from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import Dict, List, Any
from algoliasearch.search.client import SearchClient
import asyncio

LOGO_URL = "https://logo.clearbit.com/algolia.com"

@dataclass
class AlgoliaIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Algolia Integration.
    
    Attributes:
        app_id (str): Algolia Application ID
        api_key (str): Algolia Admin API Key
    """
    app_id: str
    api_key: str

class AlgoliaIntegration(Integration):
    """AlgoliaIntegration class for interacting with Algolia Search API.
    
    This class provides methods to interact with Algolia's API endpoints.
    It handles authentication and request management for indexing and searching.
    
    Attributes:
        __configuration (AlgoliaIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
        __client: Algolia SearchClient instance
    
    Example:
        >>> config = AlgoliaIntegrationConfiguration(
        ...     app_id="YOUR_APP_ID",
        ...     api_key="YOUR_ADMIN_API_KEY"
        ... )
        >>> integration = AlgoliaIntegration(config)
    """

    __configuration: AlgoliaIntegrationConfiguration

    def __init__(self, configuration: AlgoliaIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__client = SearchClient(
            self.__configuration.app_id,
            self.__configuration.api_key
        )

    def search(self, index_name: str, query: str, **kwargs) -> Dict:
        """Search records in a specified index.
        
        Args:
            index_name (str): Name of the Algolia index to search
            query (str): Search query string
            **kwargs: Additional search parameters
        
        Returns:
            Dict: Search results from Algolia
        """
        index = self.__client.init_index(index_name)
        return index.search(query, kwargs)

    def create_index(self, index_name: str, settings: Dict = None) -> Dict:
        """Create a new index in Algolia.
        
        Args:
            index_name (str): Name of the index to create
            settings (Dict, optional): Configuration settings for the index
        
        Returns:
            Dict: Response from Algolia containing the created index information
        """
        index = self.__client.init_index(index_name)
        if settings:
            index.set_settings(settings)
        return {"name": index_name, "settings": index.get_settings()}

    async def update_index(self, index_name: str, records: list) -> Dict:
        """Update records in a specified index.
        
        Args:
            index_name (str): Name of the Algolia index
            records (list): List of records to update
        
        Returns:
            Dict: Response from Algolia containing task ID
        """
        responses = []
        for record in records:
            response = await self.__client.save_object(
                index_name=index_name,
                body=record
            )
            responses.append(response)
        return responses

    async def delete_all_records(self, index_name: str) -> Dict:
        """Delete all records from a specified index.
        
        Args:
            index_name (str): Name of the Algolia index to delete records from
        
        Returns:
            Dict: Response from Algolia containing task ID
        """
        return await self.__client.clear_objects(index_name=index_name)

def as_tools(configuration: AlgoliaIntegrationConfiguration):
    """Convert Algolia integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = AlgoliaIntegration(configuration)

    class AlgoliaSearchSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to search")
        query: str = Field(..., description="Search query string")

    class AlgoliaCreateIndexSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to create")
        settings: Dict[str, Any] = Field(None, description="Optional configuration settings for the index")

    class AlgoliaUpdateRecordsSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to update records")
        records: List[Dict[str, Any]] = Field(..., description="List of records to update")

    class AlgoliaDeleteAllRecordsSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to delete records from")

    return [
        StructuredTool(
            name="algolia_search",
            description="Search for records in an Algolia index",
            func=integration.search,
            args_schema=AlgoliaSearchSchema
        ),      
        StructuredTool(
            name="algolia_create_index",
            description="Create a new index in Algolia",
            func=integration.create_index,
            args_schema=AlgoliaCreateIndexSchema
        ),
        StructuredTool(
            name="algolia_update_records",
            description="Update records in an Algolia index",
            func=lambda **kwargs: asyncio.run(integration.update_index(**kwargs)),
            args_schema=AlgoliaUpdateRecordsSchema
        ),
        StructuredTool(
            name="algolia_delete_all_records", 
            description="Delete all records from an Algolia index",
            func=lambda **kwargs: asyncio.run(integration.delete_all_records(**kwargs)),
            args_schema=AlgoliaDeleteAllRecordsSchema
        )
    ]
from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import Dict, List, Any
from algoliasearch.search_client import SearchClient

@dataclass
class AlgoliaIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Algolia Integration.
    
    Attributes:
        app_id (str): Algolia Application ID
        api_key (str): Algolia Admin API Key
        search_api_key (str): Algolia Search-Only API Key (optional)
    """
    app_id: str
    api_key: str
    search_api_key: str = None

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
    __client: SearchClient

    def __init__(self, configuration: AlgoliaIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__client = SearchClient.create(
            configuration.app_id,
            configuration.api_key
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

    def add_records(self, index_name: str, records: list) -> Dict:
        """Add records to a specified index.
        
        Args:
            index_name (str): Name of the Algolia index
            records (list): List of records to add
        
        Returns:
            Dict: Response from Algolia containing task ID
        """
        index = self.__client.init_index(index_name)
        return index.save_objects(records)

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

def as_tools(configuration: AlgoliaIntegrationConfiguration):
    """Convert Algolia integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = AlgoliaIntegration(configuration)

    class AlgoliaSearchSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to search")
        query: str = Field(..., description="Search query string")

    class AlgoliaAddRecordsSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to add records to")
        records: List[Dict[str, Any]] = Field(..., description="List of records to add")

    class AlgoliaCreateIndexSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to create")
        settings: Dict[str, Any] = Field(None, description="Optional configuration settings for the index")

    return [
        StructuredTool(
            name="algolia_search",
            description="Search for records in an Algolia index",
            func=integration.search,
            args_schema=AlgoliaSearchSchema
        ),
        StructuredTool(
            name="algolia_add_records",
            description="Add records to an Algolia index",
            func=integration.add_records,
            args_schema=AlgoliaAddRecordsSchema
        ),
        StructuredTool(
            name="algolia_create_index",
            description="Create a new index in Algolia",
            func=integration.create_index,
            args_schema=AlgoliaCreateIndexSchema
        )
    ]
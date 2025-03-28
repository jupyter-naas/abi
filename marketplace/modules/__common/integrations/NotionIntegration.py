from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
import requests
from typing import Dict, List, Optional, Any

LOGO_URL = "https://logo.clearbit.com/notion.so"

@dataclass
class NotionIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Notion integration.
    
    Attributes:
        api_key (str): Notion API key for authentication
        api_version (str): Notion API version. Defaults to "2022-06-28"
        base_url (str): Base URL for Notion API. Defaults to "https://api.notion.com/v1"
    """
    api_key: str
    api_version: str = "2022-06-28"
    base_url: str = "https://api.notion.com/v1"


class NotionIntegration(Integration):
    """Notion API integration client.
    
    This integration provides methods to interact with Notion's API endpoints.
    """

    __configuration: NotionIntegrationConfiguration

    def __init__(self, configuration: NotionIntegrationConfiguration):
        """Initialize Notion client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": self.__configuration.api_version
        }

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to Notion API.
        
        Args:
            method (str): HTTP method (GET, POST, PATCH, etc.)
            endpoint (str): API endpoint
            data (Dict, optional): Request payload. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Notion API request failed: {str(e)}")
        
    def get_page(self, page_id: str) -> Dict:
        """Retrieve a page from Notion by its ID.
        
        Args:
            page_id (str): The ID of the Notion page to retrieve
            
        Returns:
            Dict: Page data including properties and content
            
        Raises:
            IntegrationConnectionError: If the page retrieval fails
        """
        return self._make_request(
            "GET",
            f"/pages/{page_id}"
        )

    def create_property(self, key: str, value: Any, type: str = "rich_text") -> Dict:
        """Create a Notion property object.
        
        Args:
            key (str): Property name
            value (Any): Property value
            type (str): Property type (rich_text, title, etc.). Defaults to "rich_text"
            
        Returns:
            Dict: Formatted property object
        """
        if type == "title":
            return {key: {"title": [{"text": {"content": str(value)}}]}}
        return {key: {"rich_text": [{"text": {"content": str(value)}}]}}

    def create_page(self, database_id: str, properties: Dict) -> Dict:
        """Create a new page in a Notion database.
        
        Args:
            database_id (str): ID of the database to create page in
            properties (Dict): Page properties
            
        Returns:
            Dict: Created page data
        """
        data = {
            "parent": {"database_id": database_id},
            "properties": properties
        }
        return self._make_request("POST", "/pages", data)

    def update_page(self, page_id: str, properties: Dict) -> Dict:
        """Update an existing Notion page.
        
        Args:
            page_id (str): ID of the page to update
            properties (Dict): Updated properties
            
        Returns:
            Dict: Updated page data
        """
        return self._make_request("PATCH", f"/pages/{page_id}", {"properties": properties})

    def delete_page(self, page_id: str) -> Dict:
        """Archive/delete a Notion page.
        
        Args:
            page_id (str): ID of the page to delete
            
        Returns:
            Dict: Response data
        """
        return self._make_request("PATCH", f"/pages/{page_id}", {"archived": True})
    
    def get_database_id(self) -> str:
        """Retrieve the database ID from the configuration."""
        return self.__configuration.database_id

    def get_database(self, database_id: str) -> Dict:
        """Retrieve a database from Notion by its ID.
        
        Args:
            database_id (str): The ID of the Notion database to retrieve
            
        Returns:
            Dict: Database data including properties and content
            
        Raises:
            IntegrationConnectionError: If the database retrieval fails
        """
        return self._make_request(
            "GET",
            f"/databases/{database_id}"
        )

    def search_by_title(self, database_id: str, title: str) -> List[Dict]:
        """Search for pages in a database by title.
        
        Args:
            database_id (str): The ID of the database to search in
            title (str): The title text to search for
            
        Returns:
            List[Dict]: List of matching pages
            
        Raises:
            IntegrationConnectionError: If the search request fails
        """
        data = {
            "filter": {
                "property": "Title",
                "title": {
                    "contains": title
                }
            },
            "page_size": 100
        }
        
        response = self._make_request(
            "POST",
            f"/databases/{database_id}/query",
            data
        )
        
        return response.get("results", [])

def as_tools(configuration: NotionIntegrationConfiguration):
    """Convert Notion integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = NotionIntegration(configuration)
        
    class CreatePageSchema(BaseModel):
        database_id: str = Field(..., description="Notion database ID")
        title: str = Field(..., description="Page title")
        
    class GetPageSchema(BaseModel):
        page_id: str = Field(..., description="Notion page ID to retrieve")

    class UpdatePageSchema(BaseModel):
        page_id: str = Field(..., description="Notion page ID to update")
        properties: Dict = Field(..., description="Updated properties")
        
    class GetDatabaseSchema(BaseModel):
        database_id: str = Field(..., description="Notion database ID to retrieve")
        
    class SearchDatabaseSchema(BaseModel):
        database_id: str = Field(..., description="Notion database ID to search in")
        title: str = Field(..., description="Title text to search for")
        
    return [
        StructuredTool(
            name="notion_get_page",
            description="Retrieve a specific page from Notion by its ID",
            func=lambda page_id: integration.get_page(page_id),
            args_schema=GetPageSchema
        ),
        StructuredTool(
            name="notion_create_page",
            description="Create a new page in a Notion database",
            func=lambda database_id, title: integration.create_page(
                database_id,
                integration.create_property("Title", title, "title")
            ),
            args_schema=CreatePageSchema
        ),
        StructuredTool(
            name="notion_update_page",
            description="Update an existing Notion page",
            func=lambda page_id, properties: integration.update_page(page_id, properties),
            args_schema=UpdatePageSchema
        ),
        StructuredTool(
            name="notion_get_database",
            description="Retrieve a specific database from Notion by its ID",
            func=lambda database_id: integration.get_database(database_id),
            args_schema=GetDatabaseSchema
        ),
        StructuredTool(
            name="notion_search_database",
            description="Search for pages in a Notion database by title",
            func=lambda database_id, title: integration.search_by_title(database_id, title),
            args_schema=SearchDatabaseSchema
        )
    ] 
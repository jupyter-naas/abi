from abi.integration.integration import Integration, IntegrationConfiguration
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
    """Algolia integration client.

    This integration provides methods to interact with Algolia's API endpoints.
    It handles authentication and request management for indexing and searching.
    """

    __configuration: AlgoliaIntegrationConfiguration

    def __init__(self, configuration: AlgoliaIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__client = SearchClient(
            self.__configuration.app_id, self.__configuration.api_key
        )

    async def search(
        self, index_name: str, query: str, hits_per_page: int = 50, filters: str | None = None
    ):
        """Search records in a specified index.

        Args:
            index_name (str): Name of the Algolia index to search
            query (str): Search query string
            hits_per_page (int, optional): Number of results per page. Defaults to 50.
            filters (str, optional): Algolia filter string. Example: "category:Book AND price < 100"

        Returns:
            Dict: Search results from Algolia
        """
        search_params = {
            "requests": [
                {
                    "indexName": index_name,
                    "query": query,
                    "hitsPerPage": hits_per_page,
                }
            ],
        }

        if filters:
            search_params["requests"][0]["filters"] = filters

        response = await self.__client.search(search_method_params=search_params)
        return response

    def create_index(self, index_name: str, settings: Dict | None = None) -> Dict:
        """Create a new index in Algolia.

        Args:
            index_name (str): Name of the index to create
            settings (Dict, optional): Configuration settings for the index

        Returns:
            Dict: Response from Algolia containing the created index information
        """
        index = self.__client.init_index(index_name)  # type: ignore
        if settings:
            index.set_settings(settings)
        return {"name": index_name, "settings": index.get_settings()}

    def list_indexes(self):
        """List all indexes in Algolia.

        Returns:
            List of indexes from Algolia
        """
        return self.__client.list_indices()

    def delete_index(self, index_name: str) -> Dict:
        """Delete an index in Algolia.

        Args:
            index_name (str): Name of the Algolia index to delete

        Returns:
            Dict: Response from Algolia containing task ID
        """
        index = self.__client.init_index(index_name)  # type: ignore
        return index.delete()

    async def update_index(self, index_name: str, records: list):
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
                index_name=index_name, body=record
            )
            responses.append(response)
        return responses

    async def delete_all_records(self, index_name: str):
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
        filters: str | None = Field(
            None,
            description="Optional filter string. Example: 'category:Book AND price < 100'",
        )

    class AlgoliaCreateIndexSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to create")
        settings: Dict[str, Any] | None = Field(
            None, description="Optional configuration settings for the index"
        )

    class AlgoliaListIndexesSchema(BaseModel):
        pass

    class AlgoliaDeleteIndexSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to delete")

    class AlgoliaUpdateRecordsSchema(BaseModel):
        index_name: str = Field(
            ..., description="Name of the Algolia index to update records"
        )
        records: List[Dict[str, Any]] = Field(
            ..., description="List of records to update"
        )

    class AlgoliaDeleteAllRecordsSchema(BaseModel):
        index_name: str = Field(
            ..., description="Name of the Algolia index to delete records from"
        )

    return [
        StructuredTool(
            name="algolia_search_index",
            description="Search for records in an Algolia index",
            func=integration.search,
            args_schema=AlgoliaSearchSchema,
        ),
        StructuredTool(
            name="algolia_create_index",
            description="Create a new index in Algolia",
            func=integration.create_index,
            args_schema=AlgoliaCreateIndexSchema,
        ),
        StructuredTool(
            name="algolia_list_indexes",
            description="List all indexes in Algolia",
            func=integration.list_indexes,
            args_schema=AlgoliaListIndexesSchema,
        ),
        StructuredTool(
            name="algolia_delete_index",
            description="Delete an index in Algolia",
            func=integration.delete_index,
            args_schema=AlgoliaDeleteIndexSchema,
        ),
        StructuredTool(
            name="algolia_update_records",
            description="Update records in an Algolia index",
            func=lambda **kwargs: asyncio.run(integration.update_index(**kwargs)),
            args_schema=AlgoliaUpdateRecordsSchema,
        ),
        StructuredTool(
            name="algolia_delete_all_records",
            description="Delete all records from an Algolia index",
            func=lambda **kwargs: asyncio.run(integration.delete_all_records(**kwargs)),
            args_schema=AlgoliaDeleteAllRecordsSchema,
        ),
    ]

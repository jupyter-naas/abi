"""Algolia search API, async (``algoliasearch`` v4), on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.algolia.integrations``: same tool
names. ``create_index`` and ``delete_index`` used the v3 ``init_index`` API,
which v4 removed; they now call ``set_settings`` / ``delete_index``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)


def _default_client(app_id: str, api_key: str) -> Any:
    from algoliasearch.search.client import SearchClient

    return SearchClient(app_id, api_key)


def _plain(value: Any) -> Any:
    """A v4 response model as a dict (tools return JSON)."""
    to_dict = getattr(value, "to_dict", None)
    return to_dict() if callable(to_dict) else value


@dataclass
class AlgoliaIntegrationConfiguration(IntegrationConfiguration):
    """app_id: Algolia Application ID. api_key: Admin API key. client_factory:
    builds the async SearchClient (tests pass a fake)."""

    app_id: str
    api_key: str
    client_factory: Callable[[str, str], Any] = field(
        default=_default_client, repr=False
    )


class AlgoliaIntegration(Integration):
    """Search, list, create, delete indexes and save or clear records."""

    def __init__(self, configuration: AlgoliaIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration

    async def _call(self, method: str, **kwargs: Any) -> Any:
        client = self.configuration.client_factory(
            self.configuration.app_id, self.configuration.api_key
        )
        try:
            async with client:
                return _plain(await getattr(client, method)(**kwargs))
        except IntegrationConnectionError:
            raise
        except Exception as exc:  # the SDK raises its own exception types
            raise IntegrationConnectionError(
                f"Algolia API request failed: {exc!s}"
            ) from exc

    async def search(
        self,
        index_name: str,
        query: str,
        hits_per_page: int = 50,
        filters: str | None = None,
    ) -> Any:
        """Search records of an index. filters: e.g. ``"category:Book AND price < 100"``."""
        request: dict[str, Any] = {
            "indexName": index_name,
            "query": query,
            "hitsPerPage": hits_per_page,
        }
        if filters:
            request["filters"] = filters
        return await self._call("search", search_method_params={"requests": [request]})

    async def create_index(
        self, index_name: str, settings: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create an index (Algolia creates it on its first settings or record)."""
        await self._call(
            "set_settings", index_name=index_name, index_settings=settings or {}
        )
        return {
            "name": index_name,
            "settings": await self._call("get_settings", index_name=index_name),
        }

    async def list_indexes(self) -> Any:
        """All indexes of the application."""
        return await self._call("list_indices")

    async def delete_index(self, index_name: str) -> Any:
        """Delete an index and its settings."""
        return await self._call("delete_index", index_name=index_name)

    async def update_index(
        self, index_name: str, records: list[dict[str, Any]]
    ) -> list[Any]:
        """Save (add or replace) each record."""
        return [
            await self._call("save_object", index_name=index_name, body=record)
            for record in records
        ]

    async def delete_all_records(self, index_name: str) -> Any:
        """Delete every record of an index, keeping its settings."""
        return await self._call("clear_objects", index_name=index_name)


def as_tools(configuration: AlgoliaIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = AlgoliaIntegration(configuration)

    class SearchSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to search")
        query: str = Field(..., description="Search query string")
        filters: str | None = Field(
            None,
            description="Optional filter string. Example: 'category:Book AND price < 100'",
        )

    class CreateIndexSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index to create")
        settings: dict[str, Any] | None = Field(
            None, description="Optional configuration settings for the index"
        )

    class ListIndexesSchema(BaseModel):
        pass

    class IndexSchema(BaseModel):
        index_name: str = Field(..., description="Name of the Algolia index")

    class UpdateRecordsSchema(BaseModel):
        index_name: str = Field(
            ..., description="Name of the Algolia index to update records"
        )
        records: list[dict[str, Any]] = Field(
            ..., description="List of records to update"
        )

    async def search(index_name: str, query: str, filters: str | None = None) -> Any:
        return await integration.search(index_name, query, filters=filters)

    async def create_index(
        index_name: str, settings: dict[str, Any] | None = None
    ) -> Any:
        return await integration.create_index(index_name, settings)

    async def list_indexes() -> Any:
        return await integration.list_indexes()

    async def delete_index(index_name: str) -> Any:
        return await integration.delete_index(index_name)

    async def update_records(index_name: str, records: list[dict[str, Any]]) -> Any:
        return await integration.update_index(index_name, records)

    async def delete_all_records(index_name: str) -> Any:
        return await integration.delete_all_records(index_name)

    return [
        StructuredTool(
            name="algolia_search_index",
            description="Search for records in an Algolia index",
            coroutine=search,
            args_schema=SearchSchema,
        ),
        StructuredTool(
            name="algolia_create_index",
            description="Create a new index in Algolia",
            coroutine=create_index,
            args_schema=CreateIndexSchema,
        ),
        StructuredTool(
            name="algolia_list_indexes",
            description="List all indexes in Algolia",
            coroutine=list_indexes,
            args_schema=ListIndexesSchema,
        ),
        StructuredTool(
            name="algolia_delete_index",
            description="Delete an index in Algolia",
            coroutine=delete_index,
            args_schema=IndexSchema,
        ),
        StructuredTool(
            name="algolia_update_records",
            description="Update records in an Algolia index",
            coroutine=update_records,
            args_schema=UpdateRecordsSchema,
        ),
        StructuredTool(
            name="algolia_delete_all_records",
            description="Delete all records from an Algolia index",
            coroutine=delete_all_records,
            args_schema=IndexSchema,
        ),
    ]

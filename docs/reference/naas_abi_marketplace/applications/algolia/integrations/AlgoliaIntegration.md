# AlgoliaIntegration

## What it is

- A small integration wrapper around the Algolia Python `SearchClient`.
- Supports index creation/deletion/listing, searching, record updates, and clearing an index.
- Provides `as_tools()` to expose these operations as LangChain `StructuredTool` tools.

## Public API

### `AlgoliaIntegrationConfiguration`
Dataclass configuration for the integration.

- **Fields**
  - `app_id: str` — Algolia Application ID.
  - `api_key: str` — Algolia Admin API key.
  - `datastore_path: str` — Defaults to `ABIModule.get_instance().configuration.datastore_path`.

### `AlgoliaIntegration`
Integration client for Algolia.

- `__init__(configuration: AlgoliaIntegrationConfiguration)`
  - Initializes an Algolia `SearchClient` using `app_id` and `api_key`.

- `async search(index_name: str, query: str, hits_per_page: int = 50, filters: str | None = None)`
  - Searches a given index using Algolia multi-search request format.
  - Optional `filters` string is added to the request.

- `create_index(index_name: str, settings: dict | None = None) -> dict`
  - Initializes an index; optionally applies settings via `set_settings`.
  - Returns `{"name": index_name, "settings": index.get_settings()}`.

- `list_indexes()`
  - Returns `client.list_indices()`.

- `delete_index(index_name: str) -> dict`
  - Deletes an index via `index.delete()`.

- `async update_index(index_name: str, records: list)`
  - Saves each record via `client.save_object(index_name=..., body=record)`.
  - Returns a list of responses (one per record).

- `async delete_all_records(index_name: str)`
  - Clears all objects in an index via `client.clear_objects(index_name=...)`.

### `as_tools(configuration: AlgoliaIntegrationConfiguration)`
Creates LangChain tools (`StructuredTool`) wrapping an `AlgoliaIntegration` instance:

- `algolia_search_index` → `AlgoliaIntegration.search`
- `algolia_create_index` → `AlgoliaIntegration.create_index`
- `algolia_list_indexes` → `AlgoliaIntegration.list_indexes`
- `algolia_delete_index` → `AlgoliaIntegration.delete_index`
- `algolia_update_records` → runs `AlgoliaIntegration.update_index` via `asyncio.run(...)`
- `algolia_delete_all_records` → runs `AlgoliaIntegration.delete_all_records` via `asyncio.run(...)`

## Configuration/Dependencies

- **Required**
  - `algoliasearch.search.client.SearchClient`
  - `naas_abi_core.integration.integration.Integration`, `IntegrationConfiguration`
  - `naas_abi_marketplace.applications.algolia.ABIModule` (for default `datastore_path`)

- **For `as_tools()`**
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (`BaseModel`, `Field`)

- **Credentials**
  - `app_id` and `api_key` must be valid Algolia credentials (Admin key is implied by docstring).

## Usage

### Direct usage (sync + async)

```python
import asyncio
from naas_abi_marketplace.applications.algolia.integrations.AlgoliaIntegration import (
    AlgoliaIntegration,
    AlgoliaIntegrationConfiguration,
)

cfg = AlgoliaIntegrationConfiguration(app_id="YOUR_APP_ID", api_key="YOUR_API_KEY")
algolia = AlgoliaIntegration(cfg)

# Create index (sync)
algolia.create_index("products")

async def main():
    # Update records (async)
    await algolia.update_index("products", [{"objectID": "1", "name": "Book"}])

    # Search (async)
    res = await algolia.search("products", "Book", hits_per_page=10)
    print(res)

asyncio.run(main())
```

### LangChain tools

```python
from naas_abi_marketplace.applications.algolia.integrations.AlgoliaIntegration import (
    as_tools,
    AlgoliaIntegrationConfiguration,
)

cfg = AlgoliaIntegrationConfiguration(app_id="YOUR_APP_ID", api_key="YOUR_API_KEY")
tools = as_tools(cfg)

search_tool = next(t for t in tools if t.name == "algolia_search_index")
```

## Caveats

- `update_index()` saves records one-by-one; no batch API is used.
- `as_tools()` wraps async methods with `asyncio.run(...)`, which can fail if called while an event loop is already running.

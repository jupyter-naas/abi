# AlgoliaIntegration

## What it is

- A small integration wrapper around the Algolia Python `SearchClient`.
- Provides basic index management and search/update operations.
- Includes an `as_tools()` helper to expose the integration as LangChain `StructuredTool` tools.

## Public API

### `AlgoliaIntegrationConfiguration`
Dataclass configuration for the integration.

- **Fields**
  - `app_id: str` — Algolia Application ID.
  - `api_key: str` — Algolia Admin API key.
  - `datastore_path: str` — Defaults to `ABIModule.get_instance().configuration.datastore_path`.

### `AlgoliaIntegration`
Integration client.

- `__init__(configuration: AlgoliaIntegrationConfiguration)`
  - Creates an Algolia `SearchClient` using `app_id` and `api_key`.

- `async search(index_name: str, query: str, hits_per_page: int = 50, filters: str | None = None) -> Dict`
  - Searches a given index with optional Algolia `filters`.

- `create_index(index_name: str, settings: Dict | None = None) -> Dict`
  - Initializes an index; optionally applies settings via `set_settings`.
  - Returns a dict containing `name` and current `settings` (via `get_settings`).

- `list_indexes()`
  - Lists indices via `client.list_indices()`.

- `delete_index(index_name: str) -> Dict`
  - Deletes an index via `index.delete()`.

- `async update_index(index_name: str, records: list)`
  - Saves each record via `client.save_object(index_name=..., body=record)` and returns a list of responses.

- `async delete_all_records(index_name: str)`
  - Clears all objects in an index via `client.clear_objects(index_name=...)`.

### `as_tools(configuration: AlgoliaIntegrationConfiguration) -> list`
Converts the integration into LangChain tools (`StructuredTool`), providing:

- `algolia_search_index` → `AlgoliaIntegration.search`
- `algolia_create_index` → `AlgoliaIntegration.create_index`
- `algolia_list_indexes` → `AlgoliaIntegration.list_indexes`
- `algolia_delete_index` → `AlgoliaIntegration.delete_index`
- `algolia_update_records` → wraps `AlgoliaIntegration.update_index` with `asyncio.run(...)`
- `algolia_delete_all_records` → wraps `AlgoliaIntegration.delete_all_records` with `asyncio.run(...)`

## Configuration/Dependencies

- **Required packages**
  - `algoliasearch.search.client.SearchClient`
  - `naas_abi_core.integration.integration.Integration`, `IntegrationConfiguration`
  - For `as_tools()` only:
    - `langchain_core.tools.StructuredTool`
    - `pydantic` (`BaseModel`, `Field`)

- **Configuration**
  - `app_id` and `api_key` must be valid Algolia credentials.
  - `datastore_path` is present in the configuration but is not used by methods in this file.

## Usage

### Direct integration usage (async + sync)

```python
import asyncio
from naas_abi_marketplace.applications.algolia.integrations.AlgoliaIntegration import (
    AlgoliaIntegration,
    AlgoliaIntegrationConfiguration,
)

cfg = AlgoliaIntegrationConfiguration(app_id="YOUR_APP_ID", api_key="YOUR_ADMIN_API_KEY")
client = AlgoliaIntegration(cfg)

# Sync: create an index
client.create_index("products")

async def main():
    # Async: add/update records
    await client.update_index("products", [{"objectID": "1", "name": "Book"}])

    # Async: search
    res = await client.search("products", "Book", hits_per_page=10)
    print(res)

asyncio.run(main())
```

### LangChain tools

```python
from naas_abi_marketplace.applications.algolia.integrations.AlgoliaIntegration import (
    as_tools,
    AlgoliaIntegrationConfiguration,
)

cfg = AlgoliaIntegrationConfiguration(app_id="YOUR_APP_ID", api_key="YOUR_ADMIN_API_KEY")
tools = as_tools(cfg)

# Example: find the tool by name
search_tool = next(t for t in tools if t.name == "algolia_search_index")
```

## Caveats

- `update_index()` saves records one-by-one (sequential awaits); it does not use Algolia batch operations.
- In `as_tools()`, async methods are executed via `asyncio.run(...)`; this can fail if called from an environment where an event loop is already running (e.g., some notebook/async runtime contexts).

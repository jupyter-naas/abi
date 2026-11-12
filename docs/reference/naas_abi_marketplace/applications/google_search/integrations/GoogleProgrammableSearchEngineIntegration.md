# GoogleProgrammableSearchEngineIntegration

## What it is
- Integration for **Google Programmable Search Engine** (Custom Search JSON API).
- Provides:
  - Web search via the Google Custom Search API with pagination up to `num_results`.
  - HTML page text extraction from a URL using **BeautifulSoup**.
- Saves search results to a configured datastore path and caches them on filesystem for **1 day**. Extracted page text is returned only: it is neither saved nor cached.

## Public API
- `GoogleProgrammableSearchEngineIntegrationConfiguration(IntegrationConfiguration)` (dataclass)
  - Holds configuration:
    - `api_key: str` — Google API key.
    - `search_engine_id: str` — Programmable Search Engine ID (`cx`).
    - `base_url: str = "https://www.googleapis.com/customsearch/v1"` — API endpoint.
    - `datastore_path: str` — defaults to `ABIModule.get_instance().configuration.datastore_path`.

- `GoogleProgrammableSearchEngineIntegration(Integration)`
  - `__init__(configuration)`
    - Initializes storage utilities using `ABIModule.get_instance().engine.services.object_storage`.
  - `query(query: str, num_results: int = 5) -> list[dict]`
    - Calls Google Custom Search API (`requests.get`) in pages (max 10 results per request).
    - Returns the API `items` list (dicts) from the final fetched page.
    - Persists JSON to:  
      `"{datastore_path}/queries/{clean_query}/{clean_query}.json"`
    - Cached for 1 day (cache key includes `query` and `num_results`).
  - `extract_content(url: str) -> str`
    - Fetches the URL through `naas_abi_core.utils.outbound` (public addresses only, every redirect checked, 5 MB and 30 s caps) with a browser-like `User-Agent`.
    - Parses HTML, removes `script/style/noscript`, returns cleaned visible text.
    - Raises `OutboundRefused` for a URL that does not lead to a public address, and `OutboundError` when the page cannot be fetched or answers an HTTP error.

- `as_tools(configuration)`
  - Returns two LangChain `StructuredTool` tools:
    - `googlesearch_query` → wraps `integration.query`
    - `googlesearch_extract_content_from_url` → wraps `integration.extract_content`

## Configuration/Dependencies
- Requires:
  - Google API key (`api_key`)
  - Programmable Search Engine ID (`search_engine_id` / `cx`)
- Python dependencies:
  - `requests` (search API)
  - `beautifulsoup4` (`bs4`)
  - `naas_abi_core` (integration base classes, logger, cache, storage utilities)
  - `naas_abi_marketplace.applications.google_search.ABIModule`
- Caching:
  - Filesystem cache from `CacheFactory.CacheFS_find_storage(subpath="google_search")`
  - TTL: `datetime.timedelta(days=1)` for search results.

## Usage
### Basic usage
```python
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegration,
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)

config = GoogleProgrammableSearchEngineIntegrationConfiguration(
    api_key="YOUR_GOOGLE_API_KEY",
    search_engine_id="YOUR_CSE_ID",
)

g = GoogleProgrammableSearchEngineIntegration(config)

items = g.query("site:example.com documentation", num_results=5)
print(items[0].get("title"), items[0].get("link"))

text = g.extract_content("https://www.example.com/")
print(text[:200])
```

### LangChain tools
```python
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    as_tools,
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)

config = GoogleProgrammableSearchEngineIntegrationConfiguration(
    api_key="YOUR_GOOGLE_API_KEY",
    search_engine_id="YOUR_CSE_ID",
)

tools = as_tools(config)
# tools[0].name == "googlesearch_query"
# tools[1].name == "googlesearch_extract_content_from_url"
```

## Caveats
- `query()` **does not accumulate** results across pages: it overwrites `items` on each page fetch, so the returned/saved list reflects **only the last fetched page**.
- On non-200 responses, `query()` logs an error and stops, then saves whatever `items` currently contains.
- `extract_content()` may fail on non-HTML pages or blocked sites; it raises.
- Saved filenames use a “cleaned” version of query/URL (non-word chars removed, spaces → `_`), which can cause collisions for distinct inputs that clean to the same value.

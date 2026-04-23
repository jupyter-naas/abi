# GoogleProgrammableSearchEngineIntegration

## What it is
- A Google Programmable Search Engine (Custom Search JSON API) integration.
- Provides:
  - Web search with pagination (up to `num_results`).
  - HTML text extraction from a given URL (via BeautifulSoup).
- Includes optional conversion to LangChain `StructuredTool` tools.
- Persists outputs to a configured datastore path and caches results for 1 day (filesystem cache).

## Public API

### `GoogleProgrammableSearchEngineIntegrationConfiguration`
Dataclass configuration for the integration.
- `api_key: str` — Google API key.
- `search_engine_id: str` — Programmable Search Engine (CSE) ID (`cx`).
- `base_url: str = "https://www.googleapis.com/customsearch/v1"` — API endpoint.
- `datastore_path: str` — where JSON/text outputs are saved (defaults from `ABIModule` configuration).

### `GoogleProgrammableSearchEngineIntegration`
Integration class.
- `__init__(configuration)`
  - Initializes storage utilities using `ABIModule.get_instance().engine.services.object_storage`.
- `query(query: str, num_results: int = 5) -> List[dict]`
  - Calls Google Custom Search API with automatic pagination (max 10 per request).
  - Returns a list of result item dicts (from API `items`).
  - Saves results as JSON under:
    - `"{datastore_path}/queries/{clean_query}/{clean_query}.json"`
  - Cached (key includes query and num_results) for 1 day.
- `extract_content(url: str) -> str`
  - Fetches URL (with a browser-like User-Agent, timeout 30s).
  - Parses HTML, removes `script`, `style`, `noscript`, returns cleaned visible text.
  - Saves extracted text under:
    - `"{datastore_path}/extracted_content/{clean_url}/{clean_url}.txt"`
  - Cached (key includes URL) for 1 day.
  - Re-raises exceptions after logging.

### `as_tools(configuration)`
- Returns a list of LangChain `StructuredTool`:
  - `googlesearch_query` → calls `integration.query`
  - `googlesearch_extract_content_from_url` → calls `integration.extract_content`

## Configuration/Dependencies
- External dependencies:
  - `requests`
  - `beautifulsoup4` (`bs4`)
  - `naas_abi_core` (logger, Integration base classes, cache, storage utilities)
  - `naas_abi_marketplace.applications.google_search.ABIModule`
- Google Programmable Search Engine requirements:
  - Valid API key (`api_key`)
  - Search Engine ID (`search_engine_id`, `cx`)
- Caching:
  - Uses a filesystem cache created via `CacheFactory.CacheFS_find_storage(subpath="google_search")`
  - TTL: 1 day for both search results and extracted content.

## Usage

### Basic integration usage
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
- `query()` pagination logic overwrites `items` each loop iteration; it does not accumulate results across pages. The returned list (and saved JSON) will reflect only the last fetched page’s `items`.
- `query()` stops on non-200 responses (logs error and breaks) and still saves whatever `items` currently holds.
- `extract_content()` may fail on non-HTML pages or blocked sites; it logs and re-raises exceptions.
- Filenames/folder names are derived from a “cleaned” query/URL (non-word characters removed, spaces → underscores), which may cause collisions for different inputs that clean to the same string.

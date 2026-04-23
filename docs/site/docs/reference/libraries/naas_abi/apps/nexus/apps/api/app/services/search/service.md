# `SearchService`

## What it is
An async search service that:
- Provides a placeholder internal `search()` endpoint (currently returns no results).
- Performs web searches via Wikipedia or DuckDuckGo.
- Performs a private search against an ontology triple store (SPARQL), when available.
- Fetches query suggestions from Wikipedia.

## Public API

### Class: `SearchService`
- `__init__(triple_store_getter: Callable[[], Any] | None = None)`
  - Optionally injects a callable to resolve a triple store service.

- `async search(request: SearchRequestData) -> SearchResponseData`
  - Returns an empty response (`total=0`, `results=[]`, `facets={}`) echoing the query.

- `async web_search(request: WebSearchRequestData) -> WebSearchResponseData`
  - Dispatches based on `request.engine`:
    - `"wikipedia"`: queries Wikipedia API.
    - `"duckduckgo"`: queries DuckDuckGo Instant Answer API.
  - Raises `ValueError` for unknown engines.

- `async private_search(request: PrivateSearchRequestData) -> PrivateSearchResponseData`
  - If `request.source != "ontology"`: returns empty results.
  - If `request.source == "ontology"`: runs a SPARQL query against a triple store service and maps matches to `WebSearchResultData`.

- `async get_suggestions(query: str, limit: int) -> list[str]`
  - Uses Wikipedia OpenSearch API to return suggestion strings.
  - Returns `[]` on failure.

## Configuration/Dependencies
- Network client: `httpx.AsyncClient`
  - Wikipedia suggestions: 5s timeout
  - Wikipedia search: 10s timeout
  - DuckDuckGo search: 10s timeout
  - Uses default headers:
    - `User-Agent: NEXUS/1.0 (https://github.com/jravenel/nexus; search service)`

- Triple store resolution (for ontology search):
  - If `triple_store_getter` is provided, it is used.
  - Otherwise attempts: `ABIModule.get_instance().engine.services.triple_store`
  - Expected triple store interface: a `.query(sparql_query: str)` method returning iterable rows where rows support `.get(...)`.

- Data models (imported from `search__schema`):
  - Requests: `SearchRequestData`, `WebSearchRequestData`, `PrivateSearchRequestData`
  - Responses: `SearchResponseData`, `WebSearchResponseData`, `PrivateSearchResponseData`
  - Result item: `WebSearchResultData`

## Usage

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService
from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import WebSearchRequestData

async def main():
    svc = SearchService()

    resp = await svc.web_search(WebSearchRequestData(engine="wikipedia", query="SPARQL", limit=3))
    for r in resp.results:
        print(r.title, r.url)

    suggestions = await svc.get_suggestions("sparq", limit=5)
    print("Suggestions:", suggestions)

asyncio.run(main())
```

### Using ontology private search with an injected triple store

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService
from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import PrivateSearchRequestData

class DummyTripleStore:
    def query(self, sparql: str):
        return [{"uri": "http://example.org/Thing", "label": "Thing", "definition": "A thing."}]

async def main():
    svc = SearchService(triple_store_getter=lambda: DummyTripleStore())
    resp = await svc.private_search(PrivateSearchRequestData(source="ontology", query="thing"))
    print([r.title for r in resp.results])

asyncio.run(main())
```

## Caveats
- `search()` is a stub: always returns zero results.
- `web_search()` supports only `"wikipedia"` and `"duckduckgo"` engines; other values raise `ValueError`.
- Wikipedia/DuckDuckGo failures are swallowed and logged; methods return empty results on errors.
- Ontology search:
  - Returns `[]` if no triple store service can be resolved.
  - Escapes only backslashes and double quotes in the query string before embedding into SPARQL.
  - Limits SPARQL results to 100 and does not truncate `WebSearchResultData` list beyond that.
  - Relevance scoring is simple substring/exact-match based and may yield `0.0` scores for some returned rows.

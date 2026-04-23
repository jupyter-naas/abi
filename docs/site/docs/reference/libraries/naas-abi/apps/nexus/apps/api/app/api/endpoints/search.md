# `search` (Search API endpoints)

## What it is
FastAPI endpoints and Pydantic models for search features:
- A placeholder semantic search endpoint (`/`) that currently returns empty results.
- A web search endpoint (`/web`) that queries Wikipedia or DuckDuckGo.
- A placeholder private search endpoint (`/private`) that currently returns empty results.
- A suggestions endpoint (`/suggestions`) backed by Wikipedia’s OpenSearch API.

All routes are protected by an authentication dependency.

## Public API

### FastAPI router
- `router: APIRouter`
  - Configured with `dependencies=[Depends(get_current_user_required)]` to require an authenticated user for all endpoints.

### Endpoints
- `POST /` → `search(request: SearchRequest) -> SearchResponse`
  - Semantic search across knowledge sources.
  - **Current behavior:** always returns `total=0`, empty `results`, empty `facets`.

- `POST /web` → `web_search(request: WebSearchRequest) -> WebSearchResponse`
  - Searches external web sources.
  - `engine`: `"wikipedia"` or `"duckduckgo"` (validated by `Literal`).
  - Uses helper functions:
    - `search_wikipedia(...)`
    - `search_duckduckgo(...)`

- `POST /private` → `private_search(request: PrivateSearchRequest) -> PrivateSearchResponse`
  - Intended for private sources (conversations, files, knowledge graph).
  - **Current behavior:** returns empty `results`.

- `GET /suggestions` → `get_suggestions(query: str, limit: int) -> list[str]`
  - Returns search suggestions for a partial query via Wikipedia OpenSearch.
  - On failure, returns an empty list.

### Models (Pydantic)
- `SearchRequest`
  - `query: str` (1..2000)
  - `sources: list[str]` (default `["all"]`, max_length=20)
  - `limit: int` (1..100, default 20)
  - `offset: int` (>=0, default 0)
  - `filters: dict` (default `{}`)

- `SearchResult`
  - `id: str`
  - `source_type: Literal["conversation","document","entity","graph_node","app"]`
  - `title: str`, `snippet: str`, `score: float`
  - `metadata: dict` (default `{}`)
  - `created_at: datetime`

- `SearchResponse`
  - `query: str`, `total: int`, `results: list[SearchResult]`, `facets: dict` (default `{}`)

- `WebSearchRequest`
  - `query: str` (1..500)
  - `engine: Literal["wikipedia","duckduckgo"]` (default `"wikipedia"`)
  - `limit: int` (1..50, default 10)

- `WebSearchResult`
  - `id: str`, `title: str`, `snippet: str`
  - `url: str | None`
  - `relevance: float | None`
  - `metadata: dict` (default `{}`)

- `WebSearchResponse`
  - `query: str`, `engine: str`, `results: list[WebSearchResult]`

- `PrivateSearchRequest`
  - `query: str` (1..2000)
  - `source: str` (default `""`, max_length=100)

- `PrivateSearchResponse`
  - `query: str`, `source: str`, `results: list` (default `[]`)

### Internal helper functions
- `search_wikipedia(client: httpx.AsyncClient, query: str, limit: int) -> list[WebSearchResult]`
  - Calls Wikipedia `w/api.php` using `generator=search` and returns enriched results (extracts, thumbnails, full URL).
  - Errors are caught and printed; returns `[]` on failure.

- `search_duckduckgo(client: httpx.AsyncClient, query: str, limit: int) -> list[WebSearchResult]`
  - Calls DuckDuckGo Instant Answer API and builds results from `Abstract` and `RelatedTopics`.
  - Errors are caught and printed; returns up to `limit` results.

## Configuration/Dependencies
- Authentication:
  - `get_current_user_required` is applied at the router level (`Depends(...)`), so all endpoints require auth.
- External HTTP:
  - Uses `httpx.AsyncClient` with timeouts:
    - `web_search`: `timeout=10.0`
    - `get_suggestions`: `timeout=5.0`
- External services:
  - Wikipedia API: `https://en.wikipedia.org/w/api.php`
  - DuckDuckGo API: `https://api.duckduckgo.com/`
- Identification:
  - Result IDs for web search are derived from MD5 hashes (first 12 hex chars).

## Usage

### Calling the `/web` endpoint (client-side)
```python
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Add auth headers/cookies as required by get_current_user_required
        resp = await client.post("/search/web", json={
            "query": "FastAPI",
            "engine": "wikipedia",
            "limit": 5,
        })
        resp.raise_for_status()
        print(resp.json())

asyncio.run(main())
```

### Calling the `/suggestions` endpoint
```python
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        resp = await client.get("/search/suggestions", params={"query": "pyth", "limit": 5})
        resp.raise_for_status()
        print(resp.json())

asyncio.run(main())
```

## Caveats
- `POST /` (`search`) and `POST /private` (`private_search`) are placeholders and currently return empty results.
- Web search helper functions swallow exceptions and only `print(...)` errors; failures return empty results rather than raising HTTP errors.
- Default values like `metadata: dict = {}` / `filters: dict = {}` / `facets: dict = {}` are mutable defaults (Pydantic typically handles this, but it’s still a notable implementation detail).

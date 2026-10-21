# search__primary_adapter__schemas

## What it is
- A set of **Pydantic** schema models used to validate and serialize request/response payloads for search-related API endpoints.
- Covers:
  - General search (multiple source types)
  - Web search (external engines)
  - Private search (single source)

## Public API
### Models
- `SearchResult`
  - Represents a single search hit.
  - Fields: `id`, `source_type`, `title`, `snippet`, `score`, `metadata`, `created_at`.
- `SearchRequest`
  - Input parameters for general search.
  - Fields: `query`, `sources`, `limit`, `offset`, `filters`.
- `SearchResponse`
  - Response payload for general search.
  - Fields: `query`, `total`, `results`, `facets`.
- `WebSearchRequest`
  - Input parameters for web search.
  - Fields: `query`, `engine`, `limit`.
- `WebSearchResult`
  - Represents a single web search hit.
  - Fields: `id`, `title`, `snippet`, `url`, `relevance`, `metadata`.
- `WebSearchResponse`
  - Response payload for web search.
  - Fields: `query`, `engine`, `results`.
- `PrivateSearchRequest`
  - Input parameters for private search.
  - Fields: `query`, `source`.
- `PrivateSearchResponse`
  - Response payload for private search.
  - Fields: `query`, `source`, `results` (list of `WebSearchResult`).

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`, `pydantic.Field`
  - Standard library: `datetime.datetime`, `typing.Any`, `typing.Literal`
- Validation constraints (selected):
  - `SearchRequest.query`: length 1..2000
  - `SearchRequest.sources`: default `["all"]`, max items 20
  - `SearchRequest.limit`: 1..100 (default 20)
  - `SearchRequest.offset`: ≥ 0 (default 0)
  - `WebSearchRequest.query`: length 1..500
  - `WebSearchRequest.engine`: `"wikipedia"` or `"duckduckgo"` (default `"wikipedia"`)
  - `WebSearchRequest.limit`: 1..50 (default 10)
  - `PrivateSearchRequest.source`: max length 100 (default `""`)
  - `SearchResult.source_type`: one of `"conversation" | "document" | "entity" | "graph_node" | "app"`

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary.search__primary_adapter__schemas import (
    SearchRequest, SearchResult, SearchResponse,
    WebSearchRequest, WebSearchResult, WebSearchResponse,
    PrivateSearchRequest, PrivateSearchResponse,
)

# Build and validate a search request
req = SearchRequest(query="vector databases", sources=["document"], limit=10, offset=0)

# Create a response
hit = SearchResult(
    id="doc_1",
    source_type="document",
    title="Intro to Vector DBs",
    snippet="Vector databases store embeddings...",
    score=0.92,
    created_at=datetime.utcnow(),
)
resp = SearchResponse(query=req.query, total=1, results=[hit])

# Web search request/response
wreq = WebSearchRequest(query="Pydantic BaseModel", engine="wikipedia", limit=5)
wres = WebSearchResponse(
    query=wreq.query,
    engine=wreq.engine,
    results=[WebSearchResult(id="w1", title="Pydantic", snippet="...", url="https://...")],
)

# Private search request/response
preq = PrivateSearchRequest(query="internal docs", source="kb")
presp = PrivateSearchResponse(query=preq.query, source=preq.source)
```

## Caveats
- These models define **data shape and validation only**; they do not implement search logic.
- `SearchResult.source_type` is strictly limited to the declared `Literal` values.

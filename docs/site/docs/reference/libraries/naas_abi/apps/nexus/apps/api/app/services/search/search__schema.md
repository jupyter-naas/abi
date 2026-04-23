# `search__schema`

## What it is
- A small schema module defining immutable (`frozen=True`) dataclasses for search requests/responses.
- Includes types for internal search results and web/private search results.

## Public API
### Type aliases
- `SearchSourceType`: `Literal["conversation", "document", "entity", "graph_node", "app"]`
- `SearchEngine`: `Literal["wikipedia", "duckduckgo"]`

### Dataclasses
- `SearchResultData`
  - Represents a single internal search result.
  - Fields: `id`, `source_type`, `title`, `snippet`, `score`, `created_at`, `metadata`.
- `SearchRequestData`
  - Represents an internal search request.
  - Fields: `query`, `sources` (default `["all"]`), `limit` (default `20`), `offset` (default `0`), `filters`.
- `SearchResponseData`
  - Represents an internal search response.
  - Fields: `query`, `total`, `results` (`list[SearchResultData]`), `facets`.
- `WebSearchRequestData`
  - Represents a web search request.
  - Fields: `query`, `engine` (default `"wikipedia"`), `limit` (default `10`).
- `WebSearchResultData`
  - Represents a single web search result.
  - Fields: `id`, `title`, `snippet`, `url` (optional), `relevance` (optional), `metadata`.
- `WebSearchResponseData`
  - Represents a web search response.
  - Fields: `query`, `engine`, `results` (`list[WebSearchResultData]`).
- `PrivateSearchRequestData`
  - Represents a private search request.
  - Fields: `query`, `source` (default `""`).
- `PrivateSearchResponseData`
  - Represents a private search response.
  - Fields: `query`, `source`, `results` (`list[WebSearchResultData]`, default empty).

## Configuration/Dependencies
- Standard library only:
  - `dataclasses`, `datetime`, `typing` (`Any`, `Literal`)
- No runtime configuration; schemas are pure data containers.

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import (
    SearchRequestData,
    SearchResultData,
    SearchResponseData,
    WebSearchRequestData,
    WebSearchResultData,
    WebSearchResponseData,
)

req = SearchRequestData(query="vector databases", limit=5)

result = SearchResultData(
    id="doc_123",
    source_type="document",
    title="Vector DBs 101",
    snippet="A vector database stores embeddings...",
    score=0.92,
    created_at=datetime.utcnow(),
    metadata={"lang": "en"},
)

resp = SearchResponseData(query=req.query, total=1, results=[result])

web_req = WebSearchRequestData(query="Python dataclasses", engine="wikipedia", limit=3)
web_result = WebSearchResultData(
    id="w1",
    title="dataclasses — Python",
    snippet="Dataclasses provide a decorator and functions...",
    url="https://docs.python.org/3/library/dataclasses.html",
    relevance=0.8,
)
web_resp = WebSearchResponseData(query=web_req.query, engine=web_req.engine, results=[web_result])
```

## Caveats
- All dataclasses are `frozen=True` (immutable); you must create new instances instead of mutating fields.
- `SearchRequestData.sources` is typed as `list[str]` (not `list[SearchSourceType]`); validation of allowed values is not enforced by the schema itself.

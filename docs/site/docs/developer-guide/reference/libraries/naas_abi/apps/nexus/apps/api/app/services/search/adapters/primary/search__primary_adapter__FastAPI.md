# SearchFastAPIPrimaryAdapter

## What it is
- A FastAPI **primary adapter** exposing search-related HTTP endpoints via an `APIRouter`.
- Routes are protected by authentication (`get_current_user_required`) and delegate work to `SearchService` obtained via dependency injection.

## Public API
### Classes
- `SearchFastAPIPrimaryAdapter`
  - Purpose: exposes `.router` for inclusion in a FastAPI app.

### Functions / Routes (FastAPI endpoints)
- `search(request: SearchRequest, search_service: SearchService) -> SearchResponse` (`POST /`)
  - Performs a general search using `search_service.search(...)`.
- `web_search(request: WebSearchRequest, search_service: SearchService) -> WebSearchResponse` (`POST /web`)
  - Performs a web search using `search_service.web_search(...)`.
  - Converts `ValueError` from the service into `HTTPException(400)`.
- `private_search(request: PrivateSearchRequest, search_service: SearchService) -> PrivateSearchResponse` (`POST /private`)
  - Performs a private search using `search_service.private_search(...)`.
- `get_suggestions(query: str, limit: int, search_service: SearchService) -> list[str]` (`GET /suggestions`)
  - Returns query suggestions via `search_service.get_suggestions(query=..., limit=...)`.

### Internal helpers
- `_to_web_result_schema(result: WebSearchResultData) -> WebSearchResult`
  - Maps internal `WebSearchResultData` to API schema `WebSearchResult`.

## Configuration/Dependencies
- FastAPI:
  - `router = APIRouter(dependencies=[Depends(get_current_user_required)])`
    - All routes require authentication via `get_current_user_required`.
- Dependency injection:
  - `search_service: SearchService = Depends(get_search_service)`
    - `get_search_service` must provide an instance of `SearchService`.
- Schemas used:
  - Request/response models: `SearchRequest`, `SearchResponse`, `WebSearchRequest`, `WebSearchResponse`, `PrivateSearchRequest`, `PrivateSearchResponse`.
  - Service-layer data: `SearchRequestData`, `WebSearchRequestData`, `PrivateSearchRequestData`, `WebSearchResultData`.

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary.search__primary_adapter__FastAPI import (
    SearchFastAPIPrimaryAdapter,
)

app = FastAPI()

adapter = SearchFastAPIPrimaryAdapter()
app.include_router(adapter.router, prefix="/search", tags=["search"])
```

## Caveats
- `GET /suggestions` enforces:
  - `query` length: `1..200`
  - `limit` range: `1..20` (default `5`)
- `POST /web` returns HTTP 400 only when `SearchService.web_search(...)` raises `ValueError`. Other exceptions are not handled here.
- All endpoints require `get_current_user_required`; unauthenticated requests will fail according to that dependency’s behavior.

# `search` (compatibility layer)

## What it is
- A deprecated compatibility module that re-exports the search API router, request/response schemas, and service classes.
- Intended to preserve import paths during migrations.
- Primary source of truth is:
  - `naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary` (router + schemas)
  - `naas_abi.apps.nexus.apps.api.app.services.search.service` (`SearchService`)

## Public API
Re-exported symbols:

- `router`: Search API router (from `...services.search.adapters.primary`)
- Schemas / models:
  - `SearchRequest`, `SearchResponse`, `SearchResult`
  - `WebSearchRequest`, `WebSearchResponse`, `WebSearchResult`
  - `PrivateSearchRequest`, `PrivateSearchResponse`
- Service:
  - `SearchService`

Deprecated aliases (same objects as above; kept for migration clarity):
- `DeprecatedSearchRequest`, `DeprecatedSearchResponse`, `DeprecatedSearchResult`
- `DeprecatedWebSearchRequest`, `DeprecatedWebSearchResponse`, `DeprecatedWebSearchResult`
- `DeprecatedPrivateSearchRequest`, `DeprecatedPrivateSearchResponse`
- `DeprecatedSearchRouter` (alias of `router`)
- `DeprecatedSearchService` (alias of `SearchService`)

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary`
  - `naas_abi.apps.nexus.apps.api.app.services.search.service`

## Usage
Prefer importing directly from the non-compatibility modules; this file supports legacy imports.

```python
# Legacy/compat import
from naas_abi.apps.nexus.apps.api.app.api.endpoints.search import router, SearchRequest

# Migration-friendly alias also available
from naas_abi.apps.nexus.apps.api.app.api.endpoints.search import DeprecatedSearchRouter
```

## Caveats
- This module is explicitly **deprecated**; use the `...services.search...` modules for new code.

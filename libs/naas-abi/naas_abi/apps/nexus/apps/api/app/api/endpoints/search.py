"""Compatibility layer for search exports.

Deprecated: import search router and schemas from
`naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary`.
"""

from naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary import (
    PrivateSearchRequest,
    PrivateSearchResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService

# Deprecated aliases kept for migration clarity.
DeprecatedSearchRequest = SearchRequest
DeprecatedSearchResponse = SearchResponse
DeprecatedSearchResult = SearchResult
DeprecatedWebSearchRequest = WebSearchRequest
DeprecatedWebSearchResponse = WebSearchResponse
DeprecatedWebSearchResult = WebSearchResult
DeprecatedPrivateSearchRequest = PrivateSearchRequest
DeprecatedPrivateSearchResponse = PrivateSearchResponse
DeprecatedSearchRouter = router
DeprecatedSearchService = SearchService

__all__ = [
    "DeprecatedPrivateSearchRequest",
    "DeprecatedPrivateSearchResponse",
    "DeprecatedSearchRequest",
    "DeprecatedSearchResponse",
    "DeprecatedSearchResult",
    "DeprecatedSearchRouter",
    "DeprecatedSearchService",
    "DeprecatedWebSearchRequest",
    "DeprecatedWebSearchResponse",
    "DeprecatedWebSearchResult",
    "PrivateSearchRequest",
    "PrivateSearchResponse",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "SearchService",
    "WebSearchRequest",
    "WebSearchResponse",
    "WebSearchResult",
    "router",
]

"""Pre-wired SearchService builders."""

from __future__ import annotations

from typing import Any

from naas_abi_core.services.search.SearchService import SearchService
from naas_abi_core.services.search.adaptors.secondary.DuckDuckGoSearchSource import (
    DuckDuckGoSearchSource,
)
from naas_abi_core.services.search.adaptors.secondary.GraphSearchSource import (
    GraphSearchSource,
)
from naas_abi_core.services.search.adaptors.secondary.ObjectStorageSearchSource import (
    ObjectStorageSearchSource,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class SearchFactory:
    @staticmethod
    def SearchServiceWithGraph(
        triple_store: TripleStoreService,
        cache_ttl_seconds: float = 30.0,
    ) -> SearchService:
        service = SearchService(cache_ttl_seconds=cache_ttl_seconds)
        service.register_source(GraphSearchSource(triple_store))
        return service

    @staticmethod
    def SearchServiceFederated(
        triple_store: TripleStoreService | None = None,
        object_storage: Any | None = None,
        include_duckduckgo: bool = False,
        cache_ttl_seconds: float = 30.0,
    ) -> SearchService:
        """Federation across the common sources.

        Each source is optional so callers can opt in based on what their
        deployment actually exposes (e.g. no DuckDuckGo in an air-gapped env).
        """
        service = SearchService(cache_ttl_seconds=cache_ttl_seconds)
        if triple_store is not None:
            service.register_source(GraphSearchSource(triple_store))
        if object_storage is not None:
            service.register_source(ObjectStorageSearchSource(object_storage))
        if include_duckduckgo:
            service.register_source(DuckDuckGoSearchSource())
        return service

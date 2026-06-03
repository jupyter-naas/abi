"""DuckDuckGoSearchSource — live web search via DuckDuckGo.

Read-only by design: there is no index to maintain and no `index`/`remove`/
`reindex` to implement. `SearchService`'s per-source TTL cache fronts this
adapter so repeated queries (the same user typing fast, two tabs open) do
not hammer the upstream endpoint.

SCAFFOLD. Real implementation needs an HTTP client call to either the HTML
endpoint (scrape) or the Instant Answer API, with: a per-call timeout, a
User-Agent, and result normalization into `SearchHit` (title → page title,
snippet → abstract, url → result URL, kind → "webpage").
"""

from __future__ import annotations

from typing import Any, Iterator

from naas_abi_core.services.search.SearchPorts import ISearchSource, SearchHit


class DuckDuckGoSearchSource(ISearchSource):
    def __init__(self, name: str = "duckduckgo", request_timeout: float = 5.0):
        self._name = name
        self._request_timeout = request_timeout

    @property
    def name(self) -> str:
        return self._name

    def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> Iterator[SearchHit]:
        # TODO: HTTP call to DDG with `self._request_timeout`. Normalize
        # each result into SearchHit(kind="webpage", source=self._name, ...).
        # Yield lazily so the federator can start streaming before the full
        # page is processed.
        return iter([])

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SearchSourceType = Literal["conversation", "document", "entity", "graph_node", "app"]
SearchEngine = Literal["wikipedia", "duckduckgo"]


@dataclass(frozen=True)
class SearchResultData:
    id: str
    source_type: SearchSourceType
    title: str
    snippet: str
    score: float
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchRequestData:
    query: str
    sources: list[str] = field(default_factory=lambda: ["all"])
    limit: int = 20
    offset: int = 0
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResponseData:
    query: str
    total: int
    results: list[SearchResultData]
    facets: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebSearchRequestData:
    query: str
    engine: SearchEngine = "wikipedia"
    limit: int = 10


@dataclass(frozen=True)
class WebSearchResultData:
    id: str
    title: str
    snippet: str
    url: str | None = None
    relevance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebSearchResponseData:
    query: str
    engine: str
    results: list[WebSearchResultData]


@dataclass(frozen=True)
class PrivateSearchRequestData:
    query: str
    source: str = ""


@dataclass(frozen=True)
class PrivateSearchResponseData:
    query: str
    source: str
    results: list[WebSearchResultData] = field(default_factory=list)

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    id: str
    source_type: Literal["conversation", "document", "entity", "graph_node", "app"]
    title: str
    snippet: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    sources: list[str] = Field(default_factory=lambda: ["all"], max_length=20)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    filters: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]
    facets: dict[str, Any] = Field(default_factory=dict)


class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    engine: Literal["wikipedia", "duckduckgo"] = "wikipedia"
    limit: int = Field(default=10, ge=1, le=50)


class WebSearchResult(BaseModel):
    id: str
    title: str
    snippet: str
    url: str | None = None
    relevance: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebSearchResponse(BaseModel):
    query: str
    engine: str
    results: list[WebSearchResult]


class PrivateSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    source: str = Field(default="", max_length=100)


class PrivateSearchResponse(BaseModel):
    query: str
    source: str
    results: list[WebSearchResult] = Field(default_factory=list)

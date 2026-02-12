"""
Search API endpoints - Semantic search across all knowledge.
"""

import hashlib
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import \
    get_current_user_required
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class SearchResult(BaseModel):
    """Search result model."""

    id: str
    source_type: Literal["conversation", "document", "entity", "graph_node", "app"]
    title: str
    snippet: str
    score: float
    metadata: dict = {}
    created_at: datetime


class SearchRequest(BaseModel):
    """Search request model."""

    query: str = Field(..., min_length=1, max_length=2000)
    sources: list[str] = Field(default=["all"], max_length=20)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    filters: dict = {}


class SearchResponse(BaseModel):
    """Search response model."""

    query: str
    total: int
    results: list[SearchResult]
    facets: dict = {}


class WebSearchRequest(BaseModel):
    """Web search request model."""
    query: str = Field(..., min_length=1, max_length=500)
    engine: Literal["wikipedia", "duckduckgo"] = "wikipedia"
    limit: int = Field(default=10, ge=1, le=50)


class WebSearchResult(BaseModel):
    """Web search result model."""
    id: str
    title: str
    snippet: str
    url: Optional[str] = None
    relevance: Optional[float] = None
    metadata: dict = {}


class WebSearchResponse(BaseModel):
    """Web search response model."""
    query: str
    engine: str
    results: list[WebSearchResult]


@router.post("/")
async def search(request: SearchRequest) -> SearchResponse:
    """
    Perform semantic search across all knowledge sources.
    """
    return SearchResponse(
        query=request.query,
        total=0,
        results=[],
        facets={},
    )


@router.post("/web")
async def web_search(request: WebSearchRequest) -> WebSearchResponse:
    """
    Search external web sources (Wikipedia, DuckDuckGo).
    
    Supported engines:
    - wikipedia: Wikipedia article search
    - duckduckgo: DuckDuckGo instant answers
    """
    results: list[WebSearchResult] = []
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        if request.engine == "wikipedia":
            results = await search_wikipedia(client, request.query, request.limit)
        elif request.engine == "duckduckgo":
            results = await search_duckduckgo(client, request.query, request.limit)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown engine: {request.engine}")
    
    return WebSearchResponse(
        query=request.query,
        engine=request.engine,
        results=results,
    )


async def search_wikipedia(client: httpx.AsyncClient, query: str, limit: int) -> list[WebSearchResult]:
    """Search Wikipedia using their public API with images and extracts."""
    results = []
    headers = {"User-Agent": "NEXUS/1.0 (https://github.com/jravenel/nexus; demo search)"}
    
    try:
        # Use the query API with extracts and pageimages for richer results
        response = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": limit,
                "prop": "extracts|pageimages|info",
                "exintro": "1",
                "explaintext": "1",
                "exsentences": "3",
                "piprop": "thumbnail",
                "pithumbsize": "200",
                "inprop": "url",
                "format": "json",
            },
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        
        pages = data.get("query", {}).get("pages", {})
        
        # Sort by search index (relevance)
        sorted_pages = sorted(pages.values(), key=lambda p: p.get("index", 999))
        
        for i, page in enumerate(sorted_pages):
            result_id = hashlib.md5(f"wikipedia:{page.get('pageid', i)}".encode()).hexdigest()[:12]
            
            # Get thumbnail URL if available
            thumbnail = page.get("thumbnail", {}).get("source")
            
            results.append(WebSearchResult(
                id=result_id,
                title=page.get("title", ""),
                snippet=page.get("extract", "")[:500],  # Limit snippet length
                url=page.get("fullurl", f"https://en.wikipedia.org/wiki/{page.get('title', '').replace(' ', '_')}"),
                relevance=1.0 - (i * 0.05),
                metadata={
                    "source": "wikipedia",
                    "language": "en",
                    "image": thumbnail,
                    "pageid": page.get("pageid"),
                },
            ))
    except Exception as e:
        print(f"Wikipedia search error: {e}")
    
    return results


async def search_duckduckgo(client: httpx.AsyncClient, query: str, limit: int) -> list[WebSearchResult]:
    """Search DuckDuckGo using their instant answer API."""
    results = []
    headers = {"User-Agent": "NEXUS/1.0 (https://github.com/jravenel/nexus; demo search)"}
    
    try:
        # DuckDuckGo Instant Answer API
        response = await client.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            },
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        
        # Get main image if available
        main_image = data.get("Image")
        if main_image and not main_image.startswith("http"):
            main_image = f"https://duckduckgo.com{main_image}"
        
        # Add abstract if available
        if data.get("Abstract"):
            result_id = hashlib.md5(f"ddg:abstract:{query}".encode()).hexdigest()[:12]
            results.append(WebSearchResult(
                id=result_id,
                title=data.get("Heading", query),
                snippet=data.get("Abstract", ""),
                url=data.get("AbstractURL"),
                relevance=1.0,
                metadata={
                    "source": "duckduckgo",
                    "type": "abstract",
                    "source_name": data.get("AbstractSource", ""),
                    "image": main_image,
                },
            ))
        
        # Add related topics
        for i, topic in enumerate(data.get("RelatedTopics", [])[:limit-1]):
            if isinstance(topic, dict) and topic.get("Text"):
                # Get topic icon/image
                topic_icon = topic.get("Icon", {}).get("URL")
                if topic_icon and not topic_icon.startswith("http"):
                    topic_icon = f"https://duckduckgo.com{topic_icon}" if topic_icon else None
                    
                result_id = hashlib.md5(f"ddg:topic:{topic.get('FirstURL', str(i))}".encode()).hexdigest()[:12]
                results.append(WebSearchResult(
                    id=result_id,
                    title=topic.get("Text", "")[:100] + ("..." if len(topic.get("Text", "")) > 100 else ""),
                    snippet=topic.get("Text", ""),
                    url=topic.get("FirstURL"),
                    relevance=0.9 - (i * 0.05),
                    metadata={
                        "source": "duckduckgo",
                        "type": "related",
                        "image": topic_icon,
                    },
                ))
        
        # Add results from topics within categories
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and "Topics" in topic:
                for subtopic in topic.get("Topics", [])[:3]:
                    if len(results) >= limit:
                        break
                    result_id = hashlib.md5(f"ddg:subtopic:{subtopic.get('FirstURL', '')}".encode()).hexdigest()[:12]
                    results.append(WebSearchResult(
                        id=result_id,
                        title=subtopic.get("Text", "")[:100],
                        snippet=subtopic.get("Text", ""),
                        url=subtopic.get("FirstURL"),
                        relevance=0.7,
                        metadata={
                            "source": "duckduckgo",
                            "type": "category",
                            "category": topic.get("Name", ""),
                        },
                    ))
                    
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
    
    return results[:limit]


class PrivateSearchRequest(BaseModel):
    """Private search request model."""
    query: str = Field(..., min_length=1, max_length=2000)
    source: str = Field(default="", max_length=100)


class PrivateSearchResponse(BaseModel):
    """Private search response."""
    query: str
    source: str
    results: list = []


@router.post("/private")
async def private_search(request: PrivateSearchRequest) -> PrivateSearchResponse:
    """Search private sources (conversations, files, knowledge graph)."""
    # TODO: Implement private source search
    # For now return empty results
    return PrivateSearchResponse(query=request.query, source=request.source, results=[])


@router.get("/suggestions")
async def get_suggestions(
    query: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[str]:
    """Get search suggestions based on partial query."""
    # Use Wikipedia suggestions API
    suggestions = []
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": limit,
                    "namespace": "0",
                    "format": "json",
                },
                headers={
                    "User-Agent": "NEXUS/1.0 (https://github.com/jravenel/nexus; demo search)",
                },
            )
            response.raise_for_status()
            data = response.json()
            if len(data) >= 2:
                suggestions = data[1][:limit]
    except Exception as e:
        print(f"Suggestions error: {e}")
    
    return suggestions

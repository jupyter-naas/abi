"""Search FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary.search__primary_adapter__dependencies import (  # noqa: E501
    get_search_service,
)
from naas_abi.apps.nexus.apps.api.app.services.search.adapters.primary.search__primary_adapter__schemas import (  # noqa: E501
    PrivateSearchRequest,
    PrivateSearchResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
)
from naas_abi.apps.nexus.apps.api.app.services.search.search__schema import (
    PrivateSearchRequestData,
    SearchRequestData,
    WebSearchRequestData,
    WebSearchResultData,
)
from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class SearchFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def _to_web_result_schema(result: WebSearchResultData) -> WebSearchResult:
    return WebSearchResult(
        id=result.id,
        title=result.title,
        snippet=result.snippet,
        url=result.url,
        relevance=result.relevance,
        metadata=result.metadata,
    )


@router.post("/")
async def search(
    request: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    response = await search_service.search(
        SearchRequestData(
            query=request.query,
            sources=request.sources,
            limit=request.limit,
            offset=request.offset,
            filters=request.filters,
        )
    )

    return SearchResponse(
        query=response.query,
        total=response.total,
        results=[
            SearchResult(
                id=result.id,
                source_type=result.source_type,
                title=result.title,
                snippet=result.snippet,
                score=result.score,
                metadata=result.metadata,
                created_at=result.created_at,
            )
            for result in response.results
        ],
        facets=response.facets,
    )


@router.post("/web")
async def web_search(
    request: WebSearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> WebSearchResponse:
    try:
        response = await search_service.web_search(
            WebSearchRequestData(
                query=request.query,
                engine=request.engine,
                limit=request.limit,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WebSearchResponse(
        query=response.query,
        engine=response.engine,
        results=[_to_web_result_schema(result) for result in response.results],
    )


@router.post("/private")
async def private_search(
    request: PrivateSearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> PrivateSearchResponse:
    response = await search_service.private_search(
        PrivateSearchRequestData(query=request.query, source=request.source)
    )
    return PrivateSearchResponse(
        query=response.query,
        source=response.source,
        results=[_to_web_result_schema(result) for result in response.results],
    )


@router.get("/suggestions")
async def get_suggestions(
    query: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=20),
    search_service: SearchService = Depends(get_search_service),
) -> list[str]:
    return await search_service.get_suggestions(query=query, limit=limit)

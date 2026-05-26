"""
News router — wsr:NewsAggregationProcess HTTP interface.

Endpoint:
  GET /api/news — region-filtered news items from BBC / Al Jazeera / Reuters RSS
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.news import news_service

router = APIRouter(tags=["news"])


@router.get("/api/news")
async def get_news() -> JSONResponse:
    data = await news_service.get_news()
    return JSONResponse(
        content=[n.model_dump(by_alias=True) for n in data],
        headers={"Cache-Control": "public, max-age=180"},
    )

import logging

from ports.models import NewsItem
from services.news.NewsPort import INewsAdapter, INewsService

log = logging.getLogger(__name__)


class NewsService(INewsService):
    def __init__(self, adapter: INewsAdapter) -> None:
        self._adapter = adapter

    async def get_news(self) -> list[NewsItem]:
        try:
            return await self._adapter.fetch()
        except Exception as exc:
            log.warning("[news] fetch failed: %s", exc)
            return []

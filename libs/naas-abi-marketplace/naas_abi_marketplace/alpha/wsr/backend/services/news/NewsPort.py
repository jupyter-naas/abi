from ports.models import NewsItem


class INewsAdapter:
    async def fetch(self) -> list[NewsItem]:
        raise NotImplementedError


class INewsService:
    async def get_news(self) -> list[NewsItem]:
        raise NotImplementedError

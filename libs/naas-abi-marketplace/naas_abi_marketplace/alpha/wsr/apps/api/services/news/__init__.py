from services.news.adapters.rss_news import RSSNewsAdapter
from services.news.NewsService import NewsService

news_service = NewsService(adapter=RSSNewsAdapter())

__all__ = ["news_service"]

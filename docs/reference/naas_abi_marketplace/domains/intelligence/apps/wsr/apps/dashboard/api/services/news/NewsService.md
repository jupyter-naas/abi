# NewsService

## What it is
- An async service implementing `INewsService` that retrieves news items via an injected `INewsAdapter`.
- Provides a resilient `get_news()` method that logs failures and returns an empty list on error.

## Public API
- **Class: `NewsService(INewsService)`**
  - **`__init__(adapter: INewsAdapter) -> None`**
    - Stores the provided adapter used for fetching news.
  - **`async get_news() -> list[NewsItem]`**
    - Calls `await adapter.fetch()` and returns a list of `NewsItem`.
    - On any exception:
      - Logs a warning: `"[news] fetch failed: %s"`.
      - Returns `[]`.

## Configuration/Dependencies
- **Dependencies**
  - `INewsAdapter` (from `services.news.NewsPort`): must provide an async `fetch()` method returning `list[NewsItem]`.
  - `INewsService` (from `services.news.NewsPort`): interface implemented by `NewsService`.
  - `NewsItem` (from `ports.models`): item type returned by `get_news()`.
- **Logging**
  - Uses the module logger `logging.getLogger(__name__)`.
  - Ensure logging is configured if you want to capture warnings.

## Usage
```python
import asyncio
import logging

from services.news.NewsService import NewsService

logging.basicConfig(level=logging.INFO)

class DummyAdapter:
    async def fetch(self):
        return []  # should return list[NewsItem] in real adapter

async def main():
    service = NewsService(adapter=DummyAdapter())
    news = await service.get_news()
    print(news)

asyncio.run(main())
```

## Caveats
- `get_news()` suppresses all exceptions and returns an empty list; callers cannot distinguish “no news” from “fetch failed” without inspecting logs.

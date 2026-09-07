# NewsPort

## What it is
Defines async “port” (interface-style) classes for fetching and serving news items in the dashboard/news service layer.

## Public API
- `class INewsAdapter`
  - `async fetch() -> list[NewsItem]`
    - Contract for adapters that retrieve `NewsItem` objects from a data source.
- `class INewsService`
  - `async get_news() -> list[NewsItem]`
    - Contract for services that return `NewsItem` objects to callers.

## Configuration/Dependencies
- Imports and returns `ports.models.NewsItem`.

## Usage
Implement the ports by subclassing and providing concrete async methods:

```python
from ports.models import NewsItem
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.news.NewsPort import (
    INewsAdapter, INewsService,
)

class MyAdapter(INewsAdapter):
    async def fetch(self) -> list[NewsItem]:
        return []

class MyService(INewsService):
    def __init__(self, adapter: INewsAdapter):
        self.adapter = adapter

    async def get_news(self) -> list[NewsItem]:
        return await self.adapter.fetch()
```

## Caveats
- Base methods raise `NotImplementedError`; they must be overridden.
- Methods are `async` and must be awaited from an async context.

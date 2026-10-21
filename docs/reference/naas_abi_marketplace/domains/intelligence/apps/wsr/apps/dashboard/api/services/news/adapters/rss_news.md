# RSSNewsAdapter

## What it is
- An RSS news adapter that fetches and parses items from BBC, Al Jazeera, and Reuters RSS feeds.
- Filters items for relevance (region/breaking keywords), classifies severity, and returns up to 40 newest items.
- Uses a TTL cache (180 seconds) to avoid frequent refetching.

## Public API
### Class: `RSSNewsAdapter(INewsAdapter)`
- `__init__() -> None`
  - Initializes an internal `TTLCache` with `ttl_seconds=180`.
- `async fetch() -> list[NewsItem]`
  - Returns cached results when available; otherwise fetches fresh items.
  - Cache key: `"news"`.
  
### Module-level helpers (internal)
- `_parse_rss(xml: str, source: str) -> list[NewsItem]`
  - Parses RSS XML into `NewsItem` objects, applying relevance and severity logic.
- `_is_relevant(title: str) -> bool`
  - Relevance filter: title contains any region keyword or breaking keyword.
- `_detect_severity(title: str) -> SeverityLevel`
  - Severity: `"breaking"` if breaking keywords match; else `"alert"` if alert keywords match; else `"update"`.
- `_extract_cdata(text: str) -> str`
  - Extracts CDATA content or strips XML/HTML tags.

## Configuration/Dependencies
- External dependencies (from project):
  - `core.cache.TTLCache` (used for 180s TTL caching)
  - `core.http_client.get_client` (async HTTP client; must support `.get(...)` returning an object with `is_success` and `text`)
  - `ports.models.NewsItem`, `ports.models.SeverityLevel`
  - `services.news.NewsPort.INewsAdapter`
- Hardcoded RSS feeds:
  - `http://feeds.bbci.co.uk/news/world/middle_east/rss.xml` (BBC)
  - `https://www.aljazeera.com/xml/rss/all.xml` (Al Jazeera)
  - `https://feeds.reuters.com/reuters/topNews` (Reuters)
- HTTP request details:
  - `User-Agent: WSR-Intel/1.0`
  - `timeout=8` seconds per feed request

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.news.adapters.rss_news import RSSNewsAdapter

async def main():
    adapter = RSSNewsAdapter()
    items = await adapter.fetch()
    for item in items[:5]:
        print(item.title, item.source, item.severity)

asyncio.run(main())
```

## Caveats
- Only items whose titles match predefined region/breaking keywords are returned; unrelated feed items are dropped.
- Network/parse errors and non-success HTTP responses are swallowed and result in empty lists for affected feeds.
- Publication date parsing falls back to “now” (current time) if `pubDate` is missing or cannot be parsed.
- Output is capped at 40 items and sorted newest-first (by the `NewsItem` publication timestamp used in sorting).

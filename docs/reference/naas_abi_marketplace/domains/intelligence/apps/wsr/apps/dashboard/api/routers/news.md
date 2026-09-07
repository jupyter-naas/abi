# `news` Router

## What it is
- A FastAPI router that exposes a single HTTP endpoint to retrieve aggregated, region-filtered news items (sourced via RSS feeds such as BBC / Al Jazeera / Reuters) through `services.news.news_service`.

## Public API
- `router: fastapi.APIRouter`
  - Router instance tagged with `["news"]`.
- `get_news() -> fastapi.responses.JSONResponse`
  - **Route:** `GET /api/news`
  - Calls `await news_service.get_news()`.
  - Serializes each returned item using `n.model_dump(by_alias=True)`.
  - Returns a `JSONResponse` with `Cache-Control: public, max-age=180`.

## Configuration/Dependencies
- **FastAPI**
  - `fastapi.APIRouter`
  - `fastapi.responses.JSONResponse`
- **Service dependency**
  - `services.news.news_service.get_news()` must be `async` and return an iterable of objects that implement `model_dump(by_alias=True)` (e.g., Pydantic models).

## Usage
```python
from fastapi import FastAPI
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.routers.news import router as news_router

app = FastAPI()
app.include_router(news_router)
```

Call:
- `GET /api/news`

## Caveats
- If returned news items do not implement `model_dump(by_alias=True)`, response serialization will fail.
- Caching is controlled via an explicit `Cache-Control` header with a 180-second max age.

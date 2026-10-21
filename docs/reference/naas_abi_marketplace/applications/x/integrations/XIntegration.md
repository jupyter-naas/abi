# XIntegration

## What it is

A read-only integration for the X (Twitter) v2 API using bearer-token authentication. It provides methods to fetch users, tweets, timelines, followers/following, and to run recent search and recent tweet-count queries, with built-in caching, retry/backoff on transient failures, pagination helpers, and optional persistence of responses/envelopes to object storage.

## Public API

### Functions

- `slugify_query(query: str) -> str`
  - Normalizes a search query into an ASCII lowercase slug suitable for filenames/paths.

- `as_tools(configuration: XIntegrationConfiguration)`
  - Returns a list of `langchain_core.tools.StructuredTool` wrappers exposing the integration methods for agent/tool usage.

### Classes

#### `XIntegrationConfiguration(IntegrationConfiguration)`
Configuration container.

- **Fields**
  - `bearer_token: str` — OAuth 2.0 App-Only bearer token for X v2 API.
  - `base_url: str = "https://api.twitter.com/2"` — API base URL.
  - `datastore_path: str` — object-storage prefix used when persisting responses (defaults from `ABIModule` configuration).

#### `XIntegration(Integration)`
Main integration implementation.

- **Constructor**
  - `XIntegration(configuration: XIntegrationConfiguration)`
    - Initializes headers and object storage utilities.

- **User methods**
  - `get_user_by_id(user_id: str) -> dict`
    - GET `/2/users/{id}`; cached (1 day); persists JSON to `{datastore_path}/get_user_by_id/{user_id}.json`.
  - `get_user_by_username(username: str) -> dict`
    - GET `/2/users/by/username/{username}`; cached (1 day); persists JSON.
  - `get_users_by_ids(ids: list[str]) -> dict`
    - GET `/2/users?ids=...` (up to 100); cached (1 day); persists JSON (filename based on ids hash).
  - `get_users_by_usernames(usernames: list[str]) -> dict`
    - GET `/2/users/by?usernames=...` (up to 100); cached (1 day); persists JSON (filename based on usernames hash).

- **Timeline methods (paginated; uses X pagination tokens)**
  - `get_user_tweets(user_id: str, max_results: int = 100, max_pages: int | None = 1) -> dict`
    - GET `/2/users/{id}/tweets`; cached (1 day); persists merged paginated result.
  - `get_user_mentions(user_id: str, max_results: int = 100, max_pages: int | None = 1) -> dict`
    - GET `/2/users/{id}/mentions`; cached (1 day); persists merged paginated result.
  - `get_user_liked_tweets(user_id: str, max_results: int = 100, max_pages: int | None = 1) -> dict`
    - GET `/2/users/{id}/liked_tweets`; cached (1 day); persists merged paginated result.

- **Follow graph methods**
  - `get_user_followers(user_id: str, max_results: int = 100, max_pages: int | None = 1) -> dict`
    - GET `/2/users/{id}/followers`; cached (1 day); persists merged paginated result.
  - `get_user_following(user_id: str, max_results: int = 100, max_pages: int | None = 1) -> dict`
    - GET `/2/users/{id}/following`; cached (1 day); persists merged paginated result.

- **Tweet methods**
  - `get_tweet_by_id(tweet_id: str) -> dict`
    - GET `/2/tweets/{id}`; cached (1 day); persists JSON.
  - `get_tweets_by_ids(ids: list[str]) -> dict`
    - GET `/2/tweets?ids=...` (up to 100); cached (1 day); persists JSON (filename based on ids hash).

- **Search methods**
  - `search_recent_tweets(..., persist_envelope: bool = True) -> dict`
    - GET `/2/tweets/search/recent` (last 7 days).
    - Fetches up to `max_pages` pages (or exhausts when `None`) and returns an **envelope**:
      - `query`, `options`, `results` (merged pages), `started_at`, `ended_at`, `file_path`
    - Caches for 1 minute.
    - Clamps `end_time` to at most `now - 15s` to satisfy X’s “end_time must be ≥10s in the past” rule.
    - When `persist_envelope=True`, saves envelope JSON under:
      - `{datastore_path}/search_recent_tweets/{slugified_query}/{timestamp}_{slugified_query}.json`

  - `count_recent_tweets(...) -> dict`
    - GET `/2/tweets/counts/recent` (last 7 days), returning bucketed counts.
    - Returns a persisted **envelope**:
      - `query`, `options`, `results`, `total_tweet_count`, `started_at`, `ended_at`, `file_path`
    - Clamps `end_time` to at most `now - 15s`.
    - Handles pagination manually and sums `meta.total_tweet_count` across pages.
    - Cache decorator present but TTL is not set (commented out in code).

### Notable internal helpers (not part of the public API contract)

- `_make_request(...) -> dict`
  - Performs HTTP request with retry/backoff on transient status codes (429, 500, 502, 503, 504) using Fibonacci sleeps: 1, 1, 2, 3, 5 seconds.
- `_get_all_items(...) -> dict`
  - Paginates an endpoint and merges `data`, `includes`, `errors`, and selected `meta` fields; writes each page response to object storage and returns `sources` paths.

## Configuration/Dependencies

- **Required**
  - X API bearer token (`XIntegrationConfiguration.bearer_token`).
- **External libraries**
  - `requests`
  - `naas_abi_core` (Integration base classes, logger, cache services, StorageUtils)
  - `naas_abi_marketplace.applications.x.ABIModule` (for datastore path and object storage service)
- **Caching**
  - Uses a filesystem cache via `CacheFactory.CacheFS_find_storage(subpath="x")`.
  - Many methods are cached (JSON) with TTLs (commonly 1 day; search is 1 minute).
- **Persistence**
  - Saves JSON responses/envelopes to an object storage service obtained from `ABIModule.get_instance().engine.services.object_storage`.

## Usage

### Basic usage (direct integration)

```python
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
    XIntegrationConfiguration,
)

cfg = XIntegrationConfiguration(bearer_token="YOUR_X_BEARER_TOKEN")
x = XIntegration(cfg)

user = x.get_user_by_username("TwitterDev")
print(user)

env = x.search_recent_tweets(query="python lang:en -is:retweet", max_pages=1)
print(env["results"].get("meta"))
print(env["file_path"])  # object-storage path when persisted
```

### LangChain tools

```python
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegrationConfiguration,
    as_tools,
)

tools = as_tools(XIntegrationConfiguration(bearer_token="YOUR_X_BEARER_TOKEN"))
# tools is a list of StructuredTool instances (e.g., "x_search_recent_tweets")
```

## Caveats

- **`end_time` constraint**: For `/2/tweets/search/recent` and `/2/tweets/counts/recent`, `end_time` is clamped to `now - 15s` to avoid X rejecting near-real-time end times.
- **Pagination limits**:
  - Timeline/follow methods default to `max_pages=1`; pass `max_pages=None` to exhaust pagination.
  - When `_get_all_items` stops due to `max_pages`, it sets `results["meta"]["has_more"]=True` if `next_token` exists.
- **Field authorization**:
  - Some tweet fields are intentionally excluded in default `tweet_fields` for recent search due to X “Field Authorization Error” noted in code comments (owner-only metrics).

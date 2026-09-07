# XAppHubBuilder (hub.py)

## What it is
- A compatibility facade for the **X Recent Tweets** app “hub”.
- Keeps the legacy import surface (`XAppHubBuilder`, `slugify`, constants) while delegating publishing to `api.publish.publish_app` and using `SnapshotContext` for data access.

## Public API
### Constants (re-exported)
- `APP_HTML_DATA_BASE`: Base path for app HTML data (`"/app-html/x/apps/x"`).
- `DEFAULT_APP_PREFIX`, `DEFAULT_COUNT_GRAPH`, `DEFAULT_NAMESPACE`, `DEFAULT_TWEET_GRAPH`, `DEFAULT_TWEET_LIMIT`: Defaults imported from `api.common`.

### Functions (re-exported)
- `slugify(value: str) -> str`: Imported from `api.common`.

### Class: `XAppHubBuilder`
Publishes the dashboard snapshots (and optionally web assets) to object storage.

#### `__init__(object_storage_service, triple_store, *, graph_name=..., tweet_graph_name=..., namespace=..., app_prefix=...)`
- Stores services and configuration.
- Creates an internal `SnapshotContext` for timeseries/tweet snapshot generation.
- Notes:
  - `app_prefix` is stored without trailing `/` (`rstrip("/")`).

#### `publish(queries: Iterable[dict[str, Any]], *, full_users: bool = False) -> dict[str, Any]`
- Publishes typed JSON snapshots and (if present) web assets.
- Behavior:
  - Delegates to `publish_app(...)`.
  - Sets `require_web=False`, so missing `web/out/` does **not** fail publishing.
  - `full_users=True` forces a complete Users dataset rebuild; default behavior rebuilds only changed shards.

#### Compatibility helpers (non-public but present)
- `_timeseries(query_string: str) -> list[dict[str, Any]]`: Delegates to `SnapshotContext.timeseries`.
- `_tweets(query_string: str, limit: int = DEFAULT_TWEET_LIMIT) -> list[dict[str, Any]]`:
  - Returns tweets in a fixed 30-day window ending “now” (UTC) via `SnapshotContext.tweets_in_window`.
  - Comment notes this is for compatibility and prefers `tweets_in_window` in new code.

## Configuration/Dependencies
- Requires service instances:
  - `naas_abi_core.services.object_storage.ObjectStorageService.ObjectStorageService`
  - `naas_abi_core.services.triple_store.TripleStoreService.TripleStoreService`
- Uses marketplace X app modules:
  - `SnapshotContext`, defaults, and `slugify` from `naas_abi_marketplace.applications.x.apps.x.api.common`
  - `publish_app` from `naas_abi_marketplace.applications.x.apps.x.api.publish`

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.applications.x.apps.x.hub import XAppHubBuilder

object_storage = ObjectStorageService(...)
triple_store = TripleStoreService(...)

hub = XAppHubBuilder(object_storage, triple_store)

queries = [
    {"slug": "recent-tweets", "title": "Recent Tweets", "query": "SELECT ..."},
]

result = hub.publish(queries, full_users=False)
print(result)
```

## Caveats
- `publish()` is designed to **not** fail if web assets are missing (`require_web=False`); snapshot publishing still proceeds.
- `_tweets()` uses a fixed 30-day lookback window (compatibility behavior), not an unbounded history.

# publish_app

## What it is
- Orchestrates publishing an “X” app snapshot by:
  - Building snapshot scenarios and context.
  - Publishing multiple page datasets (globals, count recent tweets, search recent tweets, search users).
  - Uploading a static Next.js web export to object storage.
- Returns a structured summary of what was published.

## Public API
- `publish_app(object_storage, triple_store, queries, *, namespace=..., app_prefix=..., require_web=True, full_users=False) -> dict[str, Any]`
  - Runs all page publish steps and uploads the web export.
  - Parameters:
    - `object_storage (ObjectStorageService)`: target storage for published artifacts (including web export).
    - `triple_store (TripleStoreService)`: backing triple store used by publishing steps.
    - `queries (list[dict[str, Any]])`: query configuration passed into the snapshot context.
    - `namespace (str)`: RDF namespace used by the snapshot context (defaults from `api.common`).
    - `app_prefix (str)`: object storage prefix used for published files (defaults from `api.common`).
    - `require_web (bool)`: if `False`, allows publishing to proceed when `web/out/` is absent.
    - `full_users (bool)`: if `True`, forces rebuilding all Users shards (passed through to users publish step).
  - Returns:
    - A `dict` summary including:
      - `app_prefix`, `built_at`, `scenarios`, `queries`
      - `pages` (keys published for each page; for users, shard change counts/summary)
      - `web` (result from web export upload)
      - `index_file` (path like `"{app_prefix}/index.html"`)

## Configuration/Dependencies
- Depends on services:
  - `naas_abi_core.services.object_storage.ObjectStorageService`
  - `naas_abi_core.services.triple_store.TripleStoreService`
- Uses defaults and helpers from:
  - `naas_abi_marketplace.applications.x.apps.x.api.common`:
    - `DEFAULT_NAMESPACE`, `DEFAULT_APP_PREFIX`
    - `DEFAULT_COUNT_GRAPH`, `DEFAULT_TWEET_GRAPH`
    - `SnapshotContext`, `build_scenarios`
- Delegates publishing to:
  - `publish_globals(ctx)`
  - `count_recent_tweets.publish_page(ctx)`
  - `search_recents_tweets.publish_page(ctx)`
  - `search_users.publish_page(ctx, full=full_users)`
  - `upload_web_export(object_storage, ctx.app_prefix, required=require_web)`
- Logs completion summary via `naas_abi_core.logger`.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.applications.x.apps.x.api.publish import publish_app

object_storage = ObjectStorageService(...)  # provide implementation-specific args
triple_store = TripleStoreService(...)      # provide implementation-specific args

queries = [
    {"slug": "example-query", "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 10"},
]

summary = publish_app(
    object_storage=object_storage,
    triple_store=triple_store,
    queries=queries,
    require_web=False,   # set True if web/out/ must exist
    full_users=False,    # set True to force rebuilding all user shards
)

print(summary["index_file"])
```

## Caveats
- If `require_web=True` and the Next.js static export (`web/out/`) is missing, publishing may fail (by design, to avoid publishing against stale assets).
- The returned `pages["search_users"]` is not a list of filenames; it surfaces a users summary/counts (users data is sharded).

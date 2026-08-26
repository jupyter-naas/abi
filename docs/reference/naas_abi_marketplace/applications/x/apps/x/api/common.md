# SnapshotContext

## What it is

Shared constants and helper utilities for publishing and reading “X app” snapshots. It centralizes:

- Scenario window definitions and time helpers.
- JSON encoding/digest helpers for snapshot storage.
- SPARQL query builders/executors for:
  - hourly count buckets,
  - tweet search and faceting,
  - author/user datasets (bulk export).
- Object storage I/O helpers for snapshot files.

## Public API

### Constants

- `DEFAULT_COUNT_GRAPH`: default RDF graph URI for hourly tweet counts.
- `DEFAULT_TWEET_GRAPH`: default RDF graph URI for ingested tweets/users.
- `DEFAULT_NAMESPACE`: namespace base URI used in SPARQL prefixes.
- `DEFAULT_APP_PREFIX`: object storage prefix root for published snapshots.
- `DEFAULT_TWEET_LIMIT`: default cap for tweet table results.
- `AUTHOR_BATCH_SIZE`: usernames per SPARQL batch for bulk author operations.
- `USER_SHARD_HEX`, `USER_SHARD_COUNT`: shard parameters for per-user post files.
- `SCENARIO_SPECS`: scenario definitions (id/label/hours).
- `TWEET_COLUMN_EXPRESSIONS`: SPARQL expressions per tweet table/facet column.
- `TWEET_FACET_COLUMNS`: columns intended for distinct-value facet lists.

### Functions

- `slugify(value: str) -> str`  
  Filesystem-safe slug for a query string (lowercased, non-alnum → `_`, max 80 chars).

- `user_shard(username: str) -> str`  
  Returns shard id (first `USER_SHARD_HEX` hex chars of sha1 of normalized username).

- `encode_compact(data: dict | list) -> bytes`  
  Minified UTF-8 JSON encoding (no pretty-print).

- `content_digest(payload: bytes) -> str`  
  SHA-256 hex digest of bytes (for change detection).

- `batched(values: list[str], size: int) -> Iterator[list[str]]`  
  Yields non-empty chunks of `values` up to `size`.

- `build_scenarios(now: datetime | None = None) -> list[dict[str, str]]`  
  Builds scenario windows with `id`, `label`, `start_time`, `end_time`, floored to the hour (UTC).

- `previous_window(start_time: str, end_time: str) -> tuple[str, str]`  
  Returns an equal-duration window immediately preceding `[start_time, end_time)`.

- `extrapolate_partial_hour(partial: dict[str, Any] | None, buckets: list[dict[str, Any]]) -> dict[str, Any] | None`  
  Produces an “observed + estimated” data point for an in-progress hour using the same hour yesterday (if present). Returns `None` when inputs are missing/invalid.

- `normalize_tweet_filters(filters: dict[str, Any] | None) -> dict[str, dict[str, Any]]`  
  Normalizes column filters into `{column: {contains, values}}`, dropping unknown columns to prevent SPARQL expression injection.

### Class: `SnapshotContext`

Runtime context used by snapshot scripts to query a triple store and publish snapshot artifacts to object storage. Includes per-publish memoization for SPARQL results.

#### Constructor

- `SnapshotContext(object_storage, triple_store, *, queries, scenarios=None, graph_name=..., tweet_graph_name=..., namespace=..., app_prefix=..., tweet_limit=..., built_at=None)`

Key fields:

- `object_storage`: `ObjectStorageService`
- `triple_store`: `TripleStoreService`
- `storage`: `StorageUtils` wrapper around `object_storage`
- `queries`: list of query dicts (passed in by caller)
- `scenarios`: scenario list (defaults to `build_scenarios()`)
- `graph_name`, `tweet_graph_name`, `namespace`
- `app_prefix`: storage root prefix (stripped of trailing `/`)
- `tweet_limit`: default tweet cap for `search_tweets`
- `built_at`: publish timestamp (UTC)

#### Storage I/O

- `save_json(relative_dir: str, filename: str, data: dict | list) -> str`  
  Writes pretty JSON under `<app_prefix>/<relative_dir>/<filename>`.

- `read_json(relative_dir: str, filename: str) -> dict`  
  Reads JSON dict back from object storage; returns `{}` on missing/invalid/non-dict.

- `save_bytes(relative_dir: str, filename: str, payload: bytes) -> str`  
  Writes raw bytes under `<app_prefix>/<relative_dir>/<filename>`.

- `save_json_compact(relative_dir: str, filename: str, data: dict | list) -> str`  
  Writes minified JSON bytes (via `encode_compact`), used for large datasets.

#### Counts (hourly buckets)

- `timeseries(query_string: str) -> list[dict[str, Any]]`  
  Returns complete-hour buckets `[{start, end, count}, ...]` ordered oldest-first (memoized).

- `sum_counts_in_window(query_string: str, start_time: str, end_time: str) -> int`  
  Sums bucket counts where bucket `start` falls in `[start, end)`.

- `partial_bucket(query_string: str) -> dict[str, Any] | None`  
  Returns the “-partial” in-progress hour bucket `{start, end, count}` if present.

- `aggregate_buckets(buckets: list[dict[str, Any]], start_time: str, end_time: str, *, daily: bool) -> list[dict[str, Any]]`  
  Converts buckets into chart points for the window:
  - hourly points when `daily=False`
  - summed daily points when `daily=True`

#### Tweet search & faceting (query + window scoped)

- `count_tweets_in_window(query_string: str, start_time: str, end_time: str, *, limit: int | None = None) -> int`  
  Counts ingested tweets matching query and linked via `x:isContainedInSearchResultSet`. Optional inner `LIMIT` when `limit > 0`.

- `count_referenced_tweets_in_window(query_string: str, start_time: str, end_time: str, *, limit: int | None = None) -> int`  
  Counts referenced tweets linked via `x:isReferencedTweetOfSearchResultSet` (separate cache key from matched tweets).

- `distinct_column_values(query_string: str, start_time: str, end_time: str, column: str, *, contains: str = "", filters: dict[str, Any] | None = None, limit: int = 500) -> list[dict[str, Any]]`  
  Returns `[{value, count}, ...]` for a column across all matching tweets in the window, optionally narrowed by other column filters.

- `search_tweets(query_string: str, start_time: str, end_time: str, *, filters: dict[str, Any] | None = None, limit: int | None = None) -> list[dict[str, Any]]`  
  Returns newest-first tweet rows with fields:
  `created_at, text, url, username, location, verified_type`. Filters are applied in SPARQL before limiting (memoized by normalized filters).

- `tweets_in_window(query_string: str, start_time: str, end_time: str, *, limit: int | None = None) -> list[dict[str, Any]]`  
  Convenience alias for `search_tweets(..., filters=None)`.

#### Authors/users (graph-wide bulk)

- `all_authors() -> list[dict[str, Any]]`  
  Returns all authors with aggregates: `username, posts, last_post_at, first_post_at, location, verified_type`.

- `all_descriptions() -> dict[str, str]`  
  Returns `{username: description}`; picks the longest description per username.

- `posts_for_usernames(usernames: list[str]) -> dict[str, list[dict[str, Any]]]`  
  Returns `{username: [post, ...]}` with newest-first posts and optional `media_url` (space-separated) per tweet.

- `accounts_for_usernames(usernames: list[str]) -> dict[str, dict[str, Any]]`  
  Returns `{username: account}` from `x:XUser` profiles with optional fields and nested `metrics`. If multiple profiles exist, keeps the “richest”.

## Configuration/Dependencies

- Depends on `naas_abi_core` services:
  - `ObjectStorageService` (methods used: `get_object`, `put_object`)
  - `TripleStoreService` (method used: `query`)
  - `StorageUtils` (method used: `save_json`)
  - `logger` for warnings/info/debug
- SPARQL queries assume RDF vocabulary under `namespace` (default `http://ontology.naas.ai/x/`) and graphs:
  - counts graph (`graph_name`)
  - tweet/user graph (`tweet_graph_name`)
- Time strings passed to windowed methods are ISO-8601 strings parsed by `datetime.fromisoformat()`.

## Usage

```python
from naas_abi_marketplace.applications.x.apps.x.api.common import SnapshotContext

# object_storage: ObjectStorageService
# triple_store: TripleStoreService
ctx = SnapshotContext(
    object_storage=object_storage,
    triple_store=triple_store,
    queries=[{"query_string": "naas"}],
)

scenario = ctx.scenarios[0]
tweets = ctx.search_tweets(
    "naas",
    scenario["start_time"],
    scenario["end_time"],
    filters={"username": {"contains": "naas"}},
    limit=50,
)

ctx.save_json_compact("search", "tweets.json", tweets)
```

## Caveats

- `SnapshotContext` memoizes query results per instance and returns cached objects **without copying**; treat returned lists/dicts as read-only.
- `read_json()` only returns JSON objects (dict). JSON arrays are treated as invalid and result in `{}`.
- Time handling:
  - `build_scenarios()` floors `end_time` to the current clock hour (UTC); the in-progress hour is excluded from scenarios.
  - Window membership checks include buckets whose `start` is within `[start, end)`.
- `normalize_tweet_filters()` drops unknown columns; only columns in `TWEET_COLUMN_EXPRESSIONS` can be filtered/faceted.

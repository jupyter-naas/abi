# `search_recents_tweets.facets`

## What it is
Publishes `search_recents_tweets/facets.json`: aggregated value lists for tweet-table facet (column) filters across the full time window per query and scenario. This avoids the web app needing to query the graph to populate checkbox filter options.

## Public API
- `MAX_FACET_VALUES: int`
  - Maximum number of facet values stored per `(query_slug, scenario_id, column)` (most frequent first).
- `publish(ctx: SnapshotContext) -> dict`
  - Builds facet value lists for each configured query, scenario, and faceted column.
  - Persists the document via `ctx.save_json(...)`.
  - Returns the published document.

## Configuration/Dependencies
- Imports from `naas_abi_marketplace.applications.x.apps.x.api.common`:
  - `TWEET_FACET_COLUMNS`: iterable of column names to facet on.
  - `SnapshotContext`: context providing queries, scenarios, build time, persistence, and data access.
  - `slugify`: creates `query_slug` from query name/string.
- `SnapshotContext` is expected to provide:
  - `ctx.queries`: iterable of dict-like entries with keys like `name`, `query`.
  - `ctx.scenarios`: iterable of dict-like entries with `id`, `start_time`, `end_time`.
  - `ctx.built_at`: datetime used for `updated_at`.
  - `ctx.distinct_column_values(query, start_time, end_time, column, limit=...) -> list`
  - `ctx.save_json(app_name, filename, doc)`

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import facets

# ctx must be a fully-initialized SnapshotContext provided by the application.
doc = facets.publish(ctx)

print(doc["updated_at"])
print(len(doc["facets"]))
```

## Caveats
- Queries with an empty/whitespace-only `query` string are skipped.
- `truncated` is set to `True` when `len(values) >= MAX_FACET_VALUES` (i.e., results may be capped).

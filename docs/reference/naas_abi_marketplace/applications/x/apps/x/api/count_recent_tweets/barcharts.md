# `publish` (count_recent_tweets barcharts)

## What it is
Generates and saves `count_recent_tweets/barcharts.json` containing bar chart data for “top periods” (hours or days) per query and scenario, based on aggregated time-series buckets.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds bar chart documents for each valid query in `ctx.queries` across all `ctx.scenarios`.
  - Chooses hourly vs daily aggregation based on scenario window length (`> 48` hours → daily).
  - Ranks top 10 aggregated buckets by value (descending).
  - Persists output via `ctx.save_json("count_recent_tweets", "barcharts.json", doc)`.
  - Returns the generated document.

## Configuration/Dependencies
- Imports:
  - `datetime.fromisoformat` for scenario time window calculations.
  - `SnapshotContext` and `slugify` from `naas_abi_marketplace.applications.x.apps.x.api.common`.
- `SnapshotContext` is expected to provide:
  - Attributes:
    - `queries`: iterable of dict-like entries with at least `query` and optionally `name`.
    - `scenarios`: iterable of dict-like entries with `id`, `start_time`, `end_time` (ISO-8601 strings).
    - `built_at`: `datetime` used for `updated_at`.
  - Methods:
    - `timeseries(query_string)`: returns bucketed time-series data for a query.
    - `aggregate_buckets(buckets, start, end, daily: bool)`: returns points like `{"label": ..., "value": ...}`.
    - `save_json(app_slug, filename, doc)`: saves generated JSON.

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.count_recent_tweets.barcharts import publish

# ctx must be a SnapshotContext provided by the application runtime.
doc = publish(ctx)
print(doc["updated_at"], len(doc["barcharts"]))
```

## Caveats
- Scenario `start_time` and `end_time` must be ISO-8601 strings compatible with `datetime.fromisoformat`.
- Queries with an empty/whitespace `query` are skipped.
- Output bars include `delta` and `href` fields set to `None` (no additional computation/population in this module).

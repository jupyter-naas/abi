# kpis (count_recent_tweets)

## What it is
Publishes KPI summaries to `count_recent_tweets/kpis.json` derived from a “free counts” timeseries graph for each configured query and scenario.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds KPI entries per **query × scenario**:
    - `total`: total tweets in the scenario window and delta vs previous window
    - `mean`: mean per hour/day (depending on window length) and delta vs previous window
    - `high`: maximum bucket value in the window (with bucket label)
    - `low`: minimum bucket value in the window (with bucket label)
  - Persists the resulting document via `ctx.save_json(...)`.
  - Returns the document dict.

## Configuration/Dependencies
Relies on `naas_abi_marketplace.applications.x.apps.x.api.common`:
- `SnapshotContext`
  - Expected to provide:
    - `queries`: iterable of dicts with at least `query` (and optionally `name`)
    - `scenarios`: iterable of dicts with `id`, `start_time`, `end_time` (ISO-8601 strings)
    - `built_at`: `datetime`
    - `timeseries(query_string)`: returns bucketed time series data
    - `aggregate_buckets(buckets, start, end, daily: bool)`: returns points like `{"value": ..., "range_label": ...}`
    - `save_json(app, filename, doc)`
- `previous_window(start, end)`: computes the previous period window.
- `slugify(text)`: creates a stable slug for a query.

Other dependencies:
- Uses `datetime.fromisoformat` on `scenario["start_time"]` and `scenario["end_time"]`.

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.count_recent_tweets.kpis import publish

# ctx must be a SnapshotContext instance provided by the surrounding application
doc = publish(ctx)

# doc example shape:
# {"updated_at": "...", "kpis": [ ... ]}
```

## Caveats
- Scenarios must provide `start_time`/`end_time` parseable by `datetime.fromisoformat`.
- Aggregation switches to **daily** buckets when the scenario duration is greater than 48 hours (otherwise hourly).
- Queries with an empty/blank `query` string are skipped.
- `high`/`low` values are `None` when there are no aggregated points in the window; prior-period deltas are omitted when the previous window yields no points.

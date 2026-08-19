# `count_recent_tweets.linecharts`

## What it is
Publishes `count_recent_tweets/linecharts.json`, containing “posts over time” line chart data for each configured query and scenario. It builds current vs previous-period series, optionally adding an extrapolated in-progress hour.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds line chart payloads for each query/scenario.
  - Chooses granularity:
    - `"hour"` when the scenario window is `<= 48` hours
    - `"day"` when the scenario window is `> 48` hours
  - Adds an extrapolated partial-hour point/value when available.
  - Saves JSON via `ctx.save_json("count_recent_tweets", "linecharts.json", doc)` and returns the document.

## Configuration/Dependencies
Relies on `naas_abi_marketplace.applications.x.apps.x.api.common`:

- `SnapshotContext`
  - Expected to provide:
    - `queries`: iterable of dicts with at least `query` (string) and optional `name`
    - `scenarios`: iterable of dicts with `id`, `start_time`, `end_time` (ISO-8601 strings)
    - `built_at`: `datetime`
    - `timeseries(query_string)`
    - `partial_bucket(query_string)`
    - `aggregate_buckets(buckets, start, end, daily=bool) -> list[dict]` (points)
    - `save_json(app, filename, doc)`
- `slugify(value)` for `query_slug`
- `previous_window(start, end)` to compute the comparison window
- `extrapolate_partial_hour(partial_bucket, buckets)` to compute the in-progress hour estimate

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.count_recent_tweets import linecharts

# ctx must be a SnapshotContext provided by the application runtime.
doc = linecharts.publish(ctx)

# doc is also saved to: count_recent_tweets/linecharts.json
print(doc["updated_at"], len(doc["linecharts"]))
```

## Caveats
- Queries with an empty/whitespace `query` string are skipped.
- Partial-hour extrapolation is only applied when:
  - The estimate timestamps parse as ISO-8601, and
  - The estimated hour starts strictly before the scenario `end_time`.
- For daily charts, the partial-hour value is folded into the matching day point (if found); no new day point is created.

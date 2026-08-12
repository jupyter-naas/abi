# `linecharts` (search recent tweets)

## What it is
Publishes `search_recents_tweets/linecharts.json`, containing line chart series of ingested tweet counts over time (current window vs previous window) for each configured query and scenario.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds line chart data for each `(query, scenario)` pair.
  - Chooses hourly or daily granularity based on scenario window length.
  - Saves JSON via `ctx.save_json("search_recents_tweets", "linecharts.json", doc)`.
  - Returns the generated document.

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.applications.x.apps.x.api.common`:
  - `SnapshotContext`
    - Expected attributes/methods used:
      - `ctx.queries` (iterable of dicts with `query` and optional `name`)
      - `ctx.scenarios` (iterable of dicts with `id`, `start_time`, `end_time`)
      - `ctx.built_at` (`datetime`)
      - `ctx.tweets_in_window(query: str, start: str, end: str) -> list[dict]`
      - `ctx.save_json(app: str, filename: str, doc: dict) -> None`
  - `previous_window(start: str, end: str) -> tuple[str, str]`
  - `slugify(text: str) -> str`
- Tweet input structure:
  - Each tweet dict should include `created_at` parseable by `datetime.fromisoformat(...)`.
- Time parsing:
  - Scenario `start_time`/`end_time` must be ISO-8601 strings parseable by `datetime.fromisoformat(...)`.

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import linecharts

# ctx must be a SnapshotContext provided by the surrounding application.
doc = linecharts.publish(ctx)

# Result structure:
# {
#   "updated_at": "...",
#   "linecharts": [
#     {
#       "query_slug": "...",
#       "scenario_id": "...",
#       "granularity": "hour" | "day",
#       "series": [
#         {"id": "current", "label": "Current", "points": [...]},
#         {"id": "previous", "label": "Previous period", "points": [...]}
#       ]
#     },
#     ...
#   ]
# }
```

## Caveats
- Tweets missing `created_at` or with non-ISO `created_at` values are silently skipped.
- Granularity switches to daily when the scenario window exceeds 48 hours (`hours > 48`).
- Hourly buckets use timestamps formatted like `YYYY-MM-DDTHH:00:00+00:00`; daily points are centered at `T12:00:00+00:00` for labeling.

# barcharts (search_recents_tweets)

## What it is
Generates and publishes `search_recents_tweets/barcharts.json` containing bar chart data for:
- Top tweet authors
- Top author locations

For each configured query and scenario, it compares the current time window to the previous window and computes deltas.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds bar chart datasets per query/scenario.
  - Saves output JSON via `ctx.save_json("search_recents_tweets", "barcharts.json", doc)`.
  - Returns the generated document as a `dict`.

## Configuration/Dependencies
Depends on `naas_abi_marketplace.applications.x.apps.x.api.common`:
- `SnapshotContext`
  - Expected attributes/methods used:
    - `ctx.queries`: iterable of dict-like entries with keys like `"query"` and optional `"name"`.
    - `ctx.scenarios`: iterable of dicts with `"id"`, `"start_time"`, `"end_time"`.
    - `ctx.tweets_in_window(query: str, start, end) -> list[dict]`: returns tweet dicts (uses keys `"username"` and `"location"`).
    - `ctx.built_at`: datetime-like with `.isoformat()`.
    - `ctx.save_json(namespace: str, filename: str, data: dict)`.
- `previous_window(start, end) -> (prev_start, prev_end)`
- `slugify(text: str) -> str`

Standard library:
- `collections.Counter`

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import barcharts

# ctx must be a valid SnapshotContext instance provided by the application runtime
doc = barcharts.publish(ctx)

# doc includes updated_at and computed barcharts
print(doc["updated_at"])
print(len(doc["barcharts"]))
```

## Caveats
- Queries with an empty/whitespace `"query"` are skipped.
- Author usernames default to `"—"` when missing; those entries have `href=None`.
- Locations are only counted when `location` is non-empty after stripping.
- Only top 10 authors and top 10 locations are included per query/scenario.
- Deltas are computed against the previous window using `previous_window(start, end)`.

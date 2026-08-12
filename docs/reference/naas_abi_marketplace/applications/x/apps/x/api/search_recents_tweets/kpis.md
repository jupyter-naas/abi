# search_recents_tweets.kpis

## What it is
Publishes KPI data to `search_recents_tweets/kpis.json` for each configured query and scenario in a `SnapshotContext`. KPIs include:
- Total posts ingested (matched tweets + referenced/expanded context tweets)
- Coverage (% matched vs total count endpoint)
- Total tweets (count endpoint total)

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds KPI entries for all `ctx.queries` × `ctx.scenarios`.
  - Persists the result via `ctx.save_json("search_recents_tweets", "kpis.json", doc)`.
  - Returns the published document as a Python `dict`.

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.applications.x.apps.x.api.common`:
  - `SnapshotContext` (must provide required data and methods)
  - `previous_window(start, end)` (computes previous period window)
  - `slugify(text)` (used for `query_slug`)
- `SnapshotContext` is expected to provide:
  - Attributes:
    - `queries`: iterable of dict-like entries containing at least `query` and/or `name`
    - `scenarios`: iterable of dicts with keys `id`, `start_time`, `end_time`
    - `built_at`: datetime-like with `.isoformat()`
  - Methods:
    - `count_tweets_in_window(query, start, end, limit=0)`
    - `count_referenced_tweets_in_window(query, start, end, limit=0)`
    - `sum_counts_in_window(query, start, end)`
    - `save_json(app: str, filename: str, doc: dict)`

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets.kpis import publish

# ctx must be a fully configured SnapshotContext instance
doc = publish(ctx)
print(doc["updated_at"], len(doc["kpis"]))
```

## Caveats
- Queries with an empty/blank `query` string are skipped.
- `tweets_ingested` uses **uncapped** counts (`limit=0`) and includes both:
  - `matched`: tweets that matched the query
  - `referenced`: reply/quote/retweet originals returned via expansions and ingested as context
- `coverage` is computed using **matched-only** counts divided by `sum_counts_in_window(...)` total; referenced tweets are intentionally excluded to avoid coverage exceeding 100%.
- If the total count is `0`, coverage values are set to `None` and the hint becomes `"no count data"`.

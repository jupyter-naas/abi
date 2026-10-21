# search_recents_tweets tables publisher (`tables.py`)

## What it is
- Builds and publishes `search_recents_tweets/tables.json` containing:
  - A **tweets** table (raw tweet rows).
  - An **authors** table (tweets aggregated by author, ranked by tweet count).
- Uses a `SnapshotContext` to iterate configured queries and time-window scenarios, fetch tweets, and save the resulting JSON.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - For each non-empty query in `ctx.queries` and each scenario in `ctx.scenarios`:
    - Fetches tweets via `ctx.tweets_in_window(query, start_time, end_time)`.
    - Creates two tables:
      - `id="tweets"` with `TWEETS_COLUMNS` and the fetched tweet rows.
      - `id="authors"` with `AUTHORS_COLUMNS` and aggregated author rows.
  - Writes JSON using `ctx.save_json("search_recents_tweets", "tables.json", doc)`.
  - Returns the published document dict.

## Configuration/Dependencies
- Imports from `naas_abi_marketplace.applications.x.apps.x.api.common`:
  - `SnapshotContext` (provides queries, scenarios, built timestamp, fetching and saving helpers).
  - `slugify` (used to build `query_slug` from entry name or query).
- Expects `ctx` to provide:
  - `ctx.queries`: iterable of dicts containing at least `query` and optionally `name`.
  - `ctx.scenarios`: iterable of dicts with `id`, `start_time`, `end_time`.
  - `ctx.built_at`: datetime-like object with `.isoformat()`.
  - `ctx.tweets_in_window(query, start_time, end_time) -> list[dict]`.
  - `ctx.save_json(app, filename, doc)`.

## Usage
```python
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets.tables import publish

# ctx must be an instance of SnapshotContext with queries/scenarios configured
doc = publish(ctx)

print(doc["updated_at"])
print(len(doc["tables"]))  # 2 tables per (query, scenario)
```

## Caveats
- Queries with an empty/blank `query` string are skipped.
- Author aggregation groups by `tweet["username"]`; missing usernames are grouped under `"—"`.
- Author `location` and `verified` fields are filled from the first non-empty values encountered across that author’s tweets.
- Author ranking is by descending `tweet_count`; ranks are 1-based.

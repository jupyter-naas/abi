# XCountRecentTweetsWorkflow

## What it is
- A workflow that incrementally fetches **hourly tweet counts** from X (Twitter) for one or more X v2 search queries.
- It determines what to fetch based on **triple-store graph state** (latest mapped tweet time and existing count buckets), not wall-clock time.
- It persists count responses as JSON envelopes via `XIntegration` and returns the persisted paths:
  - **Complete-hour** envelopes (`file_paths`)
  - **In-progress-hour (partial)** envelopes (`partial_file_paths`)

## Public API

### Classes

- `XCountRecentTweetsWorkflowConfiguration(WorkflowConfiguration)`
  - Holds dependencies and settings:
    - `x_integration: XIntegration` (required)
    - `object_storage: ObjectStorageService` (required)
    - `triple_store: TripleStoreService | None` (optional; if omitted, graph-driven logic is disabled)
    - `datastore_path: str`
    - `granularity: str` (default `"hour"`)
    - `max_hours_per_run: int` (default `6`)
    - `partial_refresh_seconds: int` (default `600`)
    - `tweet_graph_name: str`, `count_graph_name: str`, `namespace: str`

- `XCountRecentTweetsWorkflowParameters(WorkflowParameters)`
  - Inputs:
    - `queries: list[str]` (one or more X v2 search queries)

- `XCountRecentTweetsWorkflow(Workflow[XCountRecentTweetsWorkflowParameters])`
  - Main workflow implementation.

### Methods (workflow)

- `run(parameters: XCountRecentTweetsWorkflowParameters) -> dict`
  - For each query:
    - Fetches missing **complete clock hours** (oldest-first, capped by `max_hours_per_run`)
    - Optionally refreshes the **current in-progress hour** (partial) when stale per `partial_refresh_seconds`
  - Returns:
    - `total_buckets`: total number of time buckets received across queries
    - `file_paths`: list of persisted envelope paths for **complete hours only**
    - `partial_file_paths`: list of dicts for partial envelopes: `{"file_path": ..., "window_end": ...}`
    - `results`: per-query breakdown (includes `buckets`, `fetched`, etc.)

- `as_tools() -> list[BaseTool]`
  - Exposes a LangChain `StructuredTool` named `x_follow_recent_tweet_counts` that calls `run(...)`.

- `latest_tweet_created_at(query: str) -> datetime | None`
  - Reads the newest mapped `x:tweet_created_at` for the query from the tweet graph (if `triple_store` is set).

- `stored_hour_starts(query: str) -> set[datetime]`
  - Reads stored complete-hour `bucket_start` values from the count graph (excludes “-partial” intervals).

- `stored_partial_end(query: str) -> datetime | None`
  - Reads the stored partial bucket’s `bucket_end` for the query (if any).

> Note: Other helpers are internal (prefixed `_`) and not intended as public API.

## Configuration/Dependencies
- Requires:
  - `XIntegration.count_recent_tweets(query, start_time, end_time, granularity)` (used to call X counts endpoint and persist envelopes; must return a `dict` envelope containing `file_path` to be useful downstream)
  - `ObjectStorageService` (used by `StorageUtils`, though this workflow primarily relies on `XIntegration` persistence)
- Optional but important:
  - `TripleStoreService` (enables graph-driven incremental windowing and gap detection). If `triple_store` is `None`, `latest_tweet_created_at()` returns `None` and the workflow will not fetch counts.

## Usage

### Minimal (programmatic)
```python
from naas_abi_marketplace.applications.x.workflows.XCountRecentTweetsWorkflow import (
    XCountRecentTweetsWorkflow,
    XCountRecentTweetsWorkflowConfiguration,
    XCountRecentTweetsWorkflowParameters,
)

# You must provide these from your runtime:
# - x_integration: XIntegration
# - object_storage: ObjectStorageService
# Optionally:
# - triple_store: TripleStoreService
workflow = XCountRecentTweetsWorkflow(
    XCountRecentTweetsWorkflowConfiguration(
        x_integration=x_integration,
        object_storage=object_storage,
        triple_store=triple_store,  # recommended
    )
)

out = workflow.run(
    XCountRecentTweetsWorkflowParameters(
        queries=["(drone OR drones OR uas OR uav) lang:en -is:retweet"]
    )
)

print(out["total_buckets"])
print(out["file_paths"])
print(out["partial_file_paths"])
```

### CLI (from `__main__`)
```bash
OXIGRAPH_URL=http://127.0.0.1:8432 uv run python \
  libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/workflows/XCountRecentTweetsWorkflow.py \
  --queries '(drone OR drones OR uas OR uav) lang:en -is:retweet'
```

## Caveats
- Counting is bounded to X “recent” availability: the workflow stays within a **7-day lookback** window.
- Complete-hour counting is driven by the **latest mapped tweet time** in the tweet graph; if no tweets are mapped for a query, it logs and returns no counts.
- Partial (in-progress hour) envelopes are **not included** in `file_paths` to avoid being deduped into the complete-hour slot; they are returned separately in `partial_file_paths`.
- Per-run backfill is capped by `max_hours_per_run` (default `6`) to limit API usage; full convergence may take multiple runs.

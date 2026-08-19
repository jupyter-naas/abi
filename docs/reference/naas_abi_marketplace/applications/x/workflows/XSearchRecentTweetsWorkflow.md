# XSearchRecentTweetsWorkflow

## What it is
- A workflow that runs one or more X (Twitter) v2 **recent search** queries **incrementally**.
- For each query, it derives `since_id` from previously persisted JSON “envelopes” stored in object storage (via a per-query cursor file). This allows fetching only tweets newer than the last run.
- Executes queries **concurrently** (one worker thread per query).
- Persists fetched results as envelope JSON files under `search_recent_tweets/<slug>/...` and maintains cursors under `_cursors/`.
- Includes a **soft spend guard** (daily/monthly caps in tweets or USD) backed by a JSON ledger under `_budget/`.

## Public API

### Classes

- `XSearchRecentTweetsWorkflowConfiguration(WorkflowConfiguration)`
  - Configuration for the workflow.
  - Key fields:
    - `x_integration: XIntegration` (required)
    - `object_storage: ObjectStorageService` (required)
    - `triple_store: TripleStoreService` (defaults to engine triple store)
    - `datastore_path: str` (defaults to module configuration)
    - `graph_name: URIRef` (defaults to module configuration)
    - Budget/spend-guard fields:
      - `budget_key`, `cost_per_tweet_usd`
      - `daily_max_tweets`, `daily_max_usd`
      - `monthly_max_tweets`, `monthly_max_usd`
    - Envelope flush thresholds:
      - `save_every_pages`, `save_every_tweets`

- `XSearchRecentTweetsWorkflowParameters(WorkflowParameters)`
  - Input parameters:
    - `queries: list[str]` (required)
    - `options: dict | None` (forwarded to `XIntegration.search_recent_tweets`, with validation; `since_id` is not allowed)
    - `persist: bool` (defaults to `True`; note: not used directly inside this workflow’s `run` method)

- `XSearchRecentTweetsWorkflow(Workflow[XSearchRecentTweetsWorkflowParameters])`
  - Main workflow class.

### Methods (XSearchRecentTweetsWorkflow)

- `run(parameters: XSearchRecentTweetsWorkflowParameters) -> dict`
  - Runs all queries (in parallel), writes envelopes, updates per-query cursor, updates budget ledger.
  - Validates `parameters.options` keys against an allowlist.
  - Returns a dict including:
    - `total_new_tweets: int`
    - `results: list[dict]` (per query: `query`, `since_id`, `new_count`, `newest_id`, `file_path`, `file_paths`, `tweets`)
    - `budget_blocked: bool`
    - `budget: dict`
    - If blocked: `budget_reason: str`

- `as_tools() -> list[BaseTool]`
  - Exposes a LangChain `StructuredTool` named `x_search_recent_tweets_incremental` that calls `run(...)`.

- `as_api(...) -> None`
  - Present but effectively a stub (only normalizes `tags`).

- Cursor helpers (useful for operators/internals):
  - `get_since_id(query: str) -> str | None`
  - `get_resume_until_id(query: str) -> str | None`
  - `get_resume_since_id(query: str) -> str | None`

## Configuration/Dependencies
- Requires:
  - `XIntegration` instance (used to call `search_recent_tweets(..., persist_envelope=False, **options)`).
  - `ObjectStorageService` (used via `StorageUtils` to list/read/write JSON files).
- Object storage layout under `datastore_path`:
  - Envelopes: `search_recent_tweets/<slugified_query>/<timestamp>_<slug>.json`
  - Per-query cursor: `_cursors/<slugified_query>.json`
  - Budget ledger: `_budget/<slugified_budget_key>.json`
- Supported `options` keys (validated):
  - `start_time`, `end_time`, `until_id`, `max_results`, `sort_order`,
    `tweet_fields`, `expansions`, `media_fields`, `poll_fields`, `user_fields`,
    `place_fields`, `max_pages`, `save_every_pages`, `save_every_tweets`
  - `since_id` is explicitly **not** accepted (derived from datastore per query).

## Usage

### Minimal Python example
```python
from naas_abi_core.engine.Engine import Engine
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration, XIntegrationConfiguration
)
from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
    XSearchRecentTweetsWorkflow,
    XSearchRecentTweetsWorkflowConfiguration,
    XSearchRecentTweetsWorkflowParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi_marketplace.applications.x"])

bearer_token = engine.services.secret.get("X_BEARER_TOKEN")
datastore_path = ABIModule.get_instance().configuration.datastore_path

x_integration = XIntegration(XIntegrationConfiguration(
    bearer_token=bearer_token,
    datastore_path=datastore_path,
))

wf = XSearchRecentTweetsWorkflow(XSearchRecentTweetsWorkflowConfiguration(
    x_integration=x_integration,
    object_storage=engine.services.object_storage,
    datastore_path=datastore_path,
))

out = wf.run(XSearchRecentTweetsWorkflowParameters(
    queries=['(FIFA World Cup) has:media lang:en -is:retweet'],
    options={"max_results": 100, "sort_order": "recency"},
    persist=True,
))

print(out["total_new_tweets"])
```

### CLI entry point (from `__main__`)
The file can be run directly; it accepts flags like `--queries`, `--max-results`, `--sort-order`, `--max-pages`, `--start-time`, `--end-time`, `--until-id`, `--no-persist`.

## Caveats
- Spend guard is **all-or-nothing** per run: if daily or monthly cap is already reached, **no X API calls are made** and the workflow returns `budget_blocked=True`.
- Cursor/budget persistence is **not atomic across processes**; the design assumes orchestrations avoid concurrent runs for the same filter.
- `persist` parameter is accepted and passed through CLI, but the workflow’s `run()` does not use it to control triple-store writes in this file (envelopes are always written by the workflow).

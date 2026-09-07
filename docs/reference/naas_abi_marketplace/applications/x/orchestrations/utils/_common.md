# `_common` (X orchestrations helpers)

## What it is
Shared utility functions/constants used by multiple X orchestrations (search workflow, event-driven ingestion, files reprocess). It centralizes:
- Dagster run gating (detecting in-progress runs)
- Running X search workflow (fetch + persist envelopes)
- Mapping persisted envelopes into the triple store
- Following and mapping recent-post count buckets
- Republishing the X app dataset after graph updates

## Public API

### Constants
- `IN_PROGRESS_RUN_STATUSES: list[dg.DagsterRunStatus]`  
  Dagster statuses treated as “still running / pending” for gating.

### Functions

- `safe_name(value: str) -> str`  
  Sanitizes a string into a Dagster-safe name fragment (non-alphanumerics → `_`; empty → `"filter"`).

- `launchpad_override(op_cfg: dict, key: str, default_value)`  
  Returns an override value from `op_cfg` when explicitly set; otherwise returns `default_value`. If the override is `None` and `default_value` is not `None`, it falls back to `default_value`.

- `has_in_progress_run(context, job_name: str) -> bool`  
  Returns `True` if there is at least one queued/starting/running Dagster run for `job_name`.

- `count_in_progress_runs(context, job_name: str, *, limit: int | None = None) -> int`  
  Counts queued/starting/running runs for `job_name`. Uses `limit` to short-circuit the query.

- `run_search_pipeline_for_file(file_path: str, *, persist: bool | None = None, graph_name: str | None = None) -> None`  
  Runs `XSearchRecentTweetsPipeline` in `file_path` mode to map a previously persisted search envelope into the graph. Intended to be idempotent.

- `search_envelope_ingested(module, file_path: str, *, graph_name: str | None = None) -> bool`  
  Checks whether an envelope path is already present in the graph by probing for a `x:SearchResultSet` with `x:file_path == file_path`.  
  Fails open (returns `False`) on errors so ingestion proceeds.

- `run_search_workflow_for_filter(filter_config, op_cfg: dict | None = None, *, max_pages: Any = _UNSET) -> list[str]`  
  Runs `XSearchRecentTweetsWorkflow` to fetch tweets for one filter and persist JSON envelopes to object storage. Returns the stored envelope paths.  
  Optional follow-ups:
  - count recent tweets (`count_recent_tweets`)
  - republish X app (`app_publish`)

- `run_search_and_map_for_query(module, filter_config, *, max_pages: Any = _UNSET, follow_counts: bool = True, graph_name: str | None = None) -> dict`  
  Runs the search workflow (fetch + save) and then maps each saved envelope inline via `run_search_pipeline_for_file`. Returns `{"query", "file_paths", "mapped"}`.

- `followed_count_entries(module) -> list[dict]`  
  Builds the list of queries shown in the “Recent Tweets” app by unioning:
  - enabled `count_recent_tweets_workflow` entries
  - `search_recent_tweets_workflow` filters that set `count_recent_tweets: true`  
  Dedupes by query string.

- `run_count_for_query(module, query: str) -> dict`  
  Runs `XCountRecentTweetsWorkflow` to fetch hourly buckets and maps them using `XCountRecentTweetsPipeline` into a dedicated named graph. Also maps “partial” (in-progress hour) counts using the pipeline’s partial mode.  
  Returns `{"query", "buckets", "mapped", "partial_mapped"}`.

- `x_app_publish_enabled(module) -> bool`  
  Reads module config `app.publish` (default `True` if missing).

- `publish_x_app(module, *, enabled: bool | None = None, full_users: bool = False) -> dict`  
  Publishes the X app datasets/snapshots for all `followed_count_entries(module)` via `XAppHubBuilder.publish(...)`.  
  - If `enabled` is not `None`, it overrides module config gating.
  - `full_users=True` forces a full rebuild of the Users dataset.

- `republish_x_app_after_pipeline(module, *, source: str, app_publish: bool, ran: bool = True) -> dict`  
  Best-effort republish wrapper after mapping pipelines:
  - Skips when `ran=False` or `app_publish=False`
  - Never raises; logs and returns failure details if publish fails

## Configuration/Dependencies

- **Dagster**: uses `SensorEvaluationContext` / `ScheduleEvaluationContext` and `.instance.get_runs(...)`.
- **ABIModule / engine services** (accessed via `ABIModule.get_instance()` or passed `module`):
  - `module.configuration.bearer_token`
  - `module.configuration.graph_name`
  - `module.configuration.ontology_namespace` (fallback: `http://ontology.naas.ai/x/`)
  - `module.configuration.app.publish` (optional; defaults to `True`)
  - `module.engine.services.object_storage`
  - `module.engine.services.triple_store`
- **Integrations/Workflows/Pipelines** (imported lazily inside functions):
  - `XIntegration`, `XIntegrationConfiguration`
  - `XSearchRecentTweetsWorkflow` (+ configuration/parameters)
  - `XSearchRecentTweetsPipeline` (+ configuration/parameters)
  - `XCountRecentTweetsWorkflow` (+ configuration/parameters)
  - `XCountRecentTweetsPipeline` (+ configuration/parameters)
  - `XAppHubBuilder`
- **SPARQL probing**: uses `SPARQLUtils` and `triple_store.query(...)`.
- **Named graph for counts**: hard-coded to `http://ontology.naas.ai/graph/x_recent_posts_count`.

## Usage

### Sanitize names and apply overrides
```python
from naas_abi_marketplace.applications.x.orchestrations.utils._common import (
    safe_name, launchpad_override
)

name = safe_name("my filter: #1")  # "my_filter___1"
max_pages = launchpad_override({"max_pages": None}, "max_pages", 10)  # 10
```

### Gate a Dagster sensor/schedule when a job is already running
```python
from naas_abi_marketplace.applications.x.orchestrations.utils._common import has_in_progress_run

def should_tick(context, job_name: str) -> bool:
    return not has_in_progress_run(context, job_name)
```

### Map an existing saved envelope file into the graph
```python
from naas_abi_marketplace.applications.x.orchestrations.utils._common import run_search_pipeline_for_file

run_search_pipeline_for_file("x/search/envelopes/2026-01-01T00:00:00Z.json")
```

### Fetch + save envelopes for a configured filter (no inline mapping)
```python
from naas_abi_marketplace.applications.x.orchestrations.utils._common import run_search_workflow_for_filter

# filter_config is an XTweetSearchWorkflowConfiguration (from module config)
file_paths = run_search_workflow_for_filter(filter_config)
```

## Caveats

- `search_envelope_ingested(...)` **fails open**: SPARQL/triple-store errors return `False`, so ingestion proceeds even if the probe fails.
- To force an **unbounded** search sweep (`max_pages=None`), pass `max_pages=None` to `run_search_workflow_for_filter(..., max_pages=None)`; a `None` value in `op_cfg` is coerced back to the filter default.
- `republish_x_app_after_pipeline(...)` never raises; publish failures are logged and surfaced only in the returned dict.

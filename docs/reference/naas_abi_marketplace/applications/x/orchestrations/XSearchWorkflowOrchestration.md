# XSearchWorkflowOrchestration

## What it is
- A Dagster orchestration that creates **one job per** `search_recent_tweets_workflow` filter in the X application configuration.
- Each job runs a single op that calls `run_search_workflow_for_filter(...)` to **fetch tweets via X v2 `search_recent_tweets` and save envelopes to object storage**.
- Triggering is **either**:
  - a **sensor** when the filter defines `interval_seconds`, or
  - a **schedule** when the filter defines `cron` (UTC).
- **Triggers are disabled by default** (`DefaultSensorStatus.STOPPED` / `DefaultScheduleStatus.STOPPED`) and must be enabled in the Dagster UI.
- A guard (`has_in_progress_run`) prevents overlapping runs for the same filter/job.

## Public API
- `class XSearchWorkflowOrchestration(DagsterOrchestration)`
  - `@classmethod New() -> XSearchWorkflowOrchestration`
    - Builds a `dagster.Definitions` containing:
      - one `JobDefinition` per configured filter,
      - exactly one trigger per filter (sensor **or** schedule),
      - no assets.
    - Skips duplicate filter names (logs a warning).

## Configuration/Dependencies
- **Configuration source**
  - `ABIModule.get_instance().configuration.search_recent_tweets_workflow` (list of `XTweetSearchWorkflowConfiguration`).
  - Each entry is expected to provide at least:
    - `name`, `query`, and either `cron` **or** `interval_seconds`.
- **Runtime dependencies (imported utilities)**
  - `run_search_workflow_for_filter(config, overrides)` — runs the underlying workflow and returns `list[str]` (op output).
  - `has_in_progress_run(context, job_name)` — used by both sensor and schedule to skip if a run is already in flight.
  - `safe_name(name)` — used to derive Dagster-safe names.
- **Op config overrides (Dagster Launchpad / run config)**
  - Each per-filter job contains one op named `x_search_workflow_op_{safe_filter_name}` with optional fields:
    - `query: str`
    - `max_results: int`
    - `max_pages: int`
    - `save_every_pages: int`
    - `save_every_tweets: int`
    - `sort_order: str`
    - `cost_per_tweet_usd: float`
    - `daily_max_tweets: int`
    - `daily_max_usd: float`
    - `monthly_max_tweets: int`
    - `monthly_max_usd: float`
    - `count_recent_tweets: bool`
    - `app_publish: bool`

## Usage
Minimal example to build Dagster definitions (typically loaded by your Dagster code location):

```python
from naas_abi_marketplace.applications.x.orchestrations.XSearchWorkflowOrchestration import (
    XSearchWorkflowOrchestration,
)

defs = XSearchWorkflowOrchestration.New().definitions
```

Example run config to override a specific filter op (replace `ai_llms` with your filter name):

```yaml
ops:
  x_search_workflow_op_ai_llms:
    config:
      max_pages: 2
      daily_max_usd: 5.0
```

## Caveats
- Only **fetch-and-save** is performed here; mapping into the graph is **not** done by this orchestration.
- Each filter has **exactly one** trigger: cron schedule or interval sensor (the config model is expected to reject setting both).
- Triggers do **not** stack runs: if the job is already running, the tick is skipped (incremental fetching relies on stored cursor/`since_id` behavior in the underlying workflow).
- Duplicate `search_recent_tweets_workflow` names are skipped (only the first is used).

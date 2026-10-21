# XCountRecentTweetsOrchestration

## What it is
A Dagster orchestration that periodically:
- fetches recent X (Twitter) post-count buckets for each enabled `count_recent_tweets_workflow` query,
- maps saved JSON envelopes into the `x_recent_posts_count` graph, and
- republishes the X app dashboard + JSON snapshots.

It exposes a single Dagster job and a single schedule (UTC cron).

## Public API
- `class XCountRecentTweetsOrchestration(DagsterOrchestration)`
  - `@classmethod New() -> XCountRecentTweetsOrchestration`
    - Builds Dagster `Definitions` containing:
      - a job named `x_count_recent_tweets` (in-process executor),
      - a schedule named `x_count_recent_tweets_hourly` using module-configured cron,
      - no assets/sensors.

## Configuration/Dependencies
- Reads configuration from `ABIModule.get_instance().configuration`:
  - `count_recent_tweets_workflow`: list of entries; only those with `enabled == True` are processed.
    - Each enabled entry must provide `query` (passed to the workflow runner).
  - `count_recent_tweets_cron`: optional cron string (UTC). Falls back to `DEFAULT_COUNT_RECENT_TWEETS_CRON`.
- Uses Dagster:
  - Job: `x_count_recent_tweets`
  - Op: `x_count_recent_tweets_op`
  - Schedule: `x_count_recent_tweets_hourly` (RUNNING only if at least one query is enabled; otherwise STOPPED).
- Runtime helpers imported inside the run cycle:
  - `naas_abi_marketplace.applications.x.orchestrations.utils.run_count_for_query`
  - `naas_abi_marketplace.applications.x.orchestrations.utils.publish_x_app`

## Usage
```python
from naas_abi_marketplace.applications.x.orchestrations.XCountRecentTweetsOrchestration import (
    XCountRecentTweetsOrchestration,
)

# Build Dagster definitions (job + schedule)
orchestration = XCountRecentTweetsOrchestration.New()

# In a Dagster code location, expose orchestration.definitions as usual.
defs = orchestration.definitions
```

## Caveats
- If no `count_recent_tweets_workflow` entries are enabled, the run cycle is a no-op and returns a summary with zeros; the schedule defaults to STOPPED in that case.
- The schedule name is fixed (`x_count_recent_tweets_hourly`); changing it would reset Dagster’s persisted RUNNING/STOPPED toggle state.

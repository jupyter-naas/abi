# `XSearchRecentTweetsEventOrchestration`

## What it is

Event-driven Dagster orchestration that ingests X “search recent tweets” envelope files into a graph.

- Creates **one Dagster job + one Dagster sensor per** configuration entry in `search_recent_tweets_event`.
- Each sensor consumes durable `ObjectPut` events and triggers mapping for matching envelope files under a configured `prefix`.
- Mapping runs `XSearchRecentTweetsPipeline` in `file_path` mode for the envelope.
- Optionally:
  - runs a follow-up “counts” step for eligible queries (best-effort; failures don’t fail ingestion),
  - republishes the X app dataset after mapping when `app_publish` is enabled.

Sensors are **disabled by default** (`STOPPED`) unless the config entry sets `enabled: true`.

## Public API

### Class: `XSearchRecentTweetsEventOrchestration(DagsterOrchestration)`
- **`New() -> XSearchRecentTweetsEventOrchestration`**
  - Builds Dagster `Definitions` containing:
    - a job per `search_recent_tweets_event` entry,
    - a sensor per entry that listens for `ObjectPut` events and submits runs.
  - Skips duplicate entry names (logs a warning and ignores duplicates).

## Configuration/Dependencies

- **Configuration source**
  - `ABIModule.get_instance().configuration.search_recent_tweets_event`: list of `XSearchRecentTweetsEventConfiguration` entries used to create sensors/jobs.
  - Relevant per-entry fields used in this module:
    - `name` (unique identifier; duplicates are skipped)
    - `prefix` (watched object-storage prefix)
    - `enabled` (controls initial sensor status)
    - `interval_seconds` (sensor evaluation interval)
    - `events_per_tick` (max events drained per tick)
    - `max_concurrent_runs` (throttles runs per job)
    - `persist` (default persist behavior for mapping)
    - `app_publish` (default app republish behavior)

- **Event service dependency**
  - Requires `module.engine.services.events_available()` and uses `module.engine.services.events.query_for_consumer(...)`.
  - Consumes `ObjectPut` events (from `ObjectStorageEventOntology`).

- **Object storage dependency**
  - Probes object existence via `module.engine.services.object_storage.get_object_metadata(prefix, key)`.
  - Handles `Exceptions.ObjectNotFound` by skipping the event.

- **Envelope selection**
  - Only objects under the watched prefix and with extensions:
    - `.json`, `.ndjson`, `.json.gz`, `.ndjson.gz`
  - Ignores events with empty keys or non-positive `size_bytes` (when provided).

- **Other utilities (internal)**
  - Uses orchestration utilities:
    - `count_in_progress_runs`, `launchpad_override`, `run_search_pipeline_for_file`,
      `safe_name`, `search_envelope_ingested`.

## Usage

### Create Dagster definitions (module wiring)

```python
from naas_abi_marketplace.applications.x.orchestrations.XSearchRecentTweetsEventOrchestration import (
    XSearchRecentTweetsEventOrchestration,
)

orchestration = XSearchRecentTweetsEventOrchestration.New()
definitions = orchestration.definitions  # Dagster Definitions with jobs+sensors
```

### Manual replay (Dagster Launchpad run config)

Run the generated job op for a specific envelope by providing `prefix` and `key`:

```yaml
ops:
  x_search_recent_tweets_pipeline_op_search_envelopes:
    config:
      prefix: x/search_recent_tweets/ai_llms
      key: 2026-06-30T12:00:00_ai_llms.json
      persist: true          # optional
      graph_name: ...        # optional
      app_publish: false     # optional
```

## Caveats

- **Sensors are STOPPED by default** unless `enabled: true` in the corresponding `search_recent_tweets_event` entry (or enabled manually in Dagster UI).
- **Concurrency gating happens before draining events** to avoid advancing the durable consumer cursor when no run slots are available.
- **Event cursor advances when draining**; for transient storage metadata probe errors the sensor “fails open” (enqueues anyway) to avoid permanently dropping events.
- **Counts follow-up is best-effort**; exceptions are logged and do not fail ingestion.
- **Duplicate config entry names are ignored** (only the first entry is used).

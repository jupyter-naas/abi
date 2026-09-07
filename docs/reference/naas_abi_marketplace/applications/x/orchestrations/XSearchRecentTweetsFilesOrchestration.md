# XSearchRecentTweetsFilesOrchestration

## What it is
A Dagster orchestration that creates **one (job, sensor) pair per configured** `search_recent_tweets_files` entry for the X application. Each job **sweeps persisted search envelope files** under a configured `prefix` and re-runs the mapping pipeline on them (optionally skipping files already mapped in the triple store). Sensors are **disabled by default** unless `enabled: true`.

## Public API
- **`class XSearchRecentTweetsFilesOrchestration(DagsterOrchestration)`**
  - **`New() -> XSearchRecentTweetsFilesOrchestration`** (classmethod)
    - Builds Dagster `Definitions` containing:
      - One job per `search_recent_tweets_files` config entry
      - One sensor per entry to trigger the corresponding job on a fixed interval

### Notable internal helpers (module-private)
- `_build_reprocess_files_job_sensor(config)`: creates the per-entry job and sensor.
- `_reprocess_files(config, op_cfg=None)`: performs listing, filtering, optional skip-existing, runs pipeline per file, and optionally republishes app snapshots.
- Envelope utilities: `_list_envelope_paths`, `_filter_paths_by_max_age`, `_mapped_file_paths`, `_envelope_path_timestamp`.

## Configuration/Dependencies
- **Dagster**
  - Jobs use `dg.in_process_executor`.
  - Sensors use `minimum_interval_seconds=config.interval_seconds`.
  - Sensor default status:
    - `RUNNING` if `config.enabled` else `STOPPED`.

- **Configuration source**
  - `ABIModule.get_instance().configuration.search_recent_tweets_files` must provide a list of `XSearchRecentTweetsFilesConfiguration` entries, each with (used fields):
    - `name`, `prefix`, `interval_seconds`, `enabled`
    - `persist`, `skip_existing`, `max_age_hours`, `app_publish`

- **Runtime services (from module engine)**
  - `module.engine.services.object_storage`: used to list objects under `prefix`.
  - `module.engine.services.triple_store`: queried via SPARQL to find already-mapped `x:file_path` values.
  - `module.configuration.graph_name` and `module.configuration.ontology_namespace`: used for graph targeting and SPARQL URI construction.

- **Per-run (Launchpad) op config schema**
  - `prefix: str` (optional) — folder to sweep; defaults to entry `config.prefix`
  - `persist: bool` (optional)
  - `skip_existing: bool` (optional)
  - `max_age_hours: int` (optional)
  - `graph_name: str` (optional) — defaults to ABI config `graph_name`
  - `app_publish: bool` (optional) — defaults to entry `config.app_publish`

## Usage
### Build Dagster definitions for this orchestration
```python
from naas_abi_marketplace.applications.x.orchestrations.XSearchRecentTweetsFilesOrchestration import (
    XSearchRecentTweetsFilesOrchestration,
)

orchestration = XSearchRecentTweetsFilesOrchestration.New()
definitions = orchestration.definitions  # Dagster Definitions (jobs + sensors)
```

### Launchpad run config example
(For an entry named `reprocess_envelopes`, overrides the job op config for that entry.)
```yaml
ops:
  x_search_recent_tweets_files_op_reprocess_envelopes:
    config:
      prefix: x/search_recent_tweets/ai_llms
      persist: true
      skip_existing: true
      max_age_hours: 24
      graph_name: http://ontology.naas.ai/graph/x
      app_publish: true
```

## Caveats
- **Sensors do not run by default**: they are created with `DefaultSensorStatus.STOPPED` unless the config entry sets `enabled: true` (or you enable them in the Dagster UI).
- **No overlapping runs per entry**: the sensor skips ticks if a prior run of the same job is still in progress.
- **Age filtering depends on filename convention**: `max_age_hours` only applies when envelope filenames start with a parseable timestamp like `<iso-ts>_<slug>.json` (supports an older underscore-based variant).
- **Triple store query failures “fail open”**: if the SPARQL query errors, the orchestration treats all files as not-yet-mapped and will attempt to reprocess them.

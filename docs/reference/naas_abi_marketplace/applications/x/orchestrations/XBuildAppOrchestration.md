# XBuildAppOrchestration

## What it is
A Dagster orchestration that periodically rebuilds the X application dashboard artifacts from the current triple-store graph state (no X API calls, no re-ingest, no re-map). It provides:

- A Dagster job: `x_build_app`
- An hourly schedule: `x_build_app_hourly` (UTC, top of the hour)
- An op: `x_build_app_op` with an optional `full_users` config flag

The schedule default status is **RUNNING** when X app publishing is enabled, otherwise **STOPPED**.

## Public API
### Class: `XBuildAppOrchestration(DagsterOrchestration)`
- **`New() -> XBuildAppOrchestration`** (classmethod)  
  Builds and returns a `DagsterOrchestration` containing:
  - Job `x_build_app` (in-process executor)
  - Schedule `x_build_app_hourly` (`cron_schedule="0 * * * *"`, timezone `UTC`)
  - No assets, sensors

### Job/Op (Dagster definitions created inside `New()`)
- **Job:** `x_build_app`  
  Runs the rebuild cycle.
- **Op:** `x_build_app_op`  
  Executes the rebuild cycle and returns a summary dict.

### Internal helper
- **`_run_build_cycle(full_users: bool = False) -> dict`**  
  Calls `publish_x_app(module, full_users=...)` and returns `{"app": <publish_result>}`.

## Configuration/Dependencies
### Op config (`x_build_app_op`)
- `full_users` (bool, optional; default `False`)  
  - When `False`: incremental behavior (only rebuild user shards whose authors changed).
  - When `True`: rebuild all Users shards to pick up profile edits without a new post.

### Key dependencies
- `dagster`
- `naas_abi_core.logger`
- `naas_abi_core.orchestrations.DagsterOrchestration`
- `naas_abi_marketplace.applications.x.ABIModule`
- `naas_abi_marketplace.applications.x.orchestrations.utils`:
  - `publish_x_app`
  - `x_app_publish_enabled`

## Usage
### In Dagster (Launchpad run config)
Run job `x_build_app` with optional op config:

```yaml
ops:
  x_build_app_op:
    config:
      full_users: true
```

### Programmatic creation (registering definitions)
```python
from naas_abi_marketplace.applications.x.orchestrations.XBuildAppOrchestration import (
    XBuildAppOrchestration,
)

orchestration = XBuildAppOrchestration.New()
defs = orchestration.definitions  # Dagster Definitions to register
```

## Caveats
- Uses Dagster **in-process** executor (intended to avoid subprocess bootstrapping/races with backing stores).
- Schedule default status depends on `x_app_publish_enabled(module)`; it may be created **STOPPED** and require enabling in Dagster UI.

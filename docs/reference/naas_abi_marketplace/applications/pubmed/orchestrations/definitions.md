# `definitions` (Dagster `Definitions`)

## What it is
A minimal Dagster definitions module that registers empty sets of jobs, sensors, and assets, and exposes a `dagster.Definitions` object named `definitions`.

## Public API
- `jobs: TJobs`
  - List of Dagster jobs (currently empty).
- `sensors: TSensors`
  - List of Dagster sensors (currently empty).
- `assets: TAssets`
  - List of Dagster assets (currently empty).
- `definitions: dagster.Definitions`
  - The Dagster `Definitions` object created from `jobs`, `sensors`, and `assets`.

## Configuration/Dependencies
- Depends on:
  - `dagster`
  - Dagster typing aliases imported from `dagster._core.definitions.definitions_class`: `TJobs`, `TSensors`, `TAssets`

## Usage
Minimal import to access the `Definitions` object:

```python
from naas_abi_marketplace.applications.pubmed.orchestrations.definitions import definitions

# Use `definitions` with Dagster tooling (e.g., code locations / deployments)
print(definitions)
```

## Caveats
- No jobs, sensors, or assets are defined in this module; all lists are empty.

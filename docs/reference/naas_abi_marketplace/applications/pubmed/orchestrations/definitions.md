# `definitions` (Dagster `Definitions`)

## What it is
A minimal Dagster definitions module for the PubMed orchestration package. It exports a `dagster.Definitions` object with no jobs, sensors, or assets registered.

## Public API
- `jobs: TJobs`
  - Empty list of Dagster jobs (`[]`).
- `sensors: TSensors`
  - Empty list of Dagster sensors (`[]`).
- `assets: TAssets`
  - Empty list of Dagster assets (`[]`).
- `definitions: dagster.Definitions`
  - Constructed as `dagster.Definitions(jobs=jobs, sensors=sensors, assets=assets)`.

## Configuration/Dependencies
- Dependencies:
  - `dagster`
  - Typing aliases from `dagster._core.definitions.definitions_class`: `TJobs`, `TSensors`, `TAssets`

## Usage
```python
from naas_abi_marketplace.applications.pubmed.orchestrations.definitions import definitions

print(definitions)
```

## Caveats
- No jobs, sensors, or assets are included; all collections are empty.

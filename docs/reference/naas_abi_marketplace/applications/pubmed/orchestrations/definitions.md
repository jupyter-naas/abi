# `definitions` (Dagster `Definitions`)

## What it is
A minimal Dagster definitions module that exports an empty `dagster.Definitions` object for the PubMed orchestration package.

## Public API
- `jobs: TJobs`
  - Empty list of Dagster jobs.
- `sensors: TSensors`
  - Empty list of Dagster sensors.
- `assets: TAssets`
  - Empty list of Dagster assets.
- `definitions: dagster.Definitions`
  - `dagster.Definitions(jobs=jobs, sensors=sensors, assets=assets)`.

## Configuration/Dependencies
- Dependencies:
  - `dagster`
  - `dagster._core.definitions.definitions_class` typing aliases: `TJobs`, `TSensors`, `TAssets`

## Usage
```python
from naas_abi_marketplace.applications.pubmed.orchestrations.definitions import definitions

print(definitions)
```

## Caveats
- No jobs, sensors, or assets are registered; all collections are empty.

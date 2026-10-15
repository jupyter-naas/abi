# `{{orchestration_name_pascal}}Orchestration`

## What it is
- A minimal Dagster orchestration template.
- Implements Dagster `Definitions` wiring via `DagsterOrchestration`.
- Intended for projects **without NATS** (legacy; marked for removal in the next major).

## Public API
- `class {{orchestration_name_pascal}}Orchestration(DagsterOrchestration)`
  - `@classmethod New() -> "{{orchestration_name_pascal}}Orchestration"`
    - Returns a new instance configured with:
      - `dg.Definitions(assets=[], schedules=[], jobs=[], sensors=[])`

## Configuration/Dependencies
- Requires:
  - `dagster` (imported as `dg`)
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
- Notes:
  - Docstring indicates it needs the `naas-abi-core[dagster]` extra.

## Usage
```python
from your_module_path import {{orchestration_name_pascal}}Orchestration

orchestration = {{orchestration_name_pascal}}Orchestration.New()
```

## Caveats
- `New()` creates an orchestration with **no assets, schedules, jobs, or sensors**; it is a blank starting point.
- Marked as **legacy** (“to be removed in the next major”).

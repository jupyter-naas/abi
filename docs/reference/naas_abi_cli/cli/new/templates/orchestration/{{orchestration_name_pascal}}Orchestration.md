# `{{orchestration_name_pascal}}Orchestration`

## What it is
- A Dagster-based orchestration template class.
- Subclasses `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`.
- Provides a factory constructor that creates an instance with an empty `dagster.Definitions` (no assets, schedules, jobs, or sensors).

## Public API
- `class {{orchestration_name_pascal}}Orchestration(DagsterOrchestration)`
  - `@classmethod New() -> "{{orchestration_name_pascal}}Orchestration"`
    - Creates and returns a new orchestration instance configured with:
      - `dg.Definitions(assets=[], schedules=[], jobs=[], sensors=[])`

## Configuration/Dependencies
- Dependencies:
  - `dagster` (imported as `dg`)
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
- No runtime configuration in this template; all Dagster definition lists are initialized empty.

## Usage
```python
from your_module_path import {{orchestration_name_pascal}}Orchestration

orch = {{orchestration_name_pascal}}Orchestration.New()
```

## Caveats
- The returned orchestration has no assets, schedules, jobs, or sensors; it is a blank starting point that must be extended/populated elsewhere to do meaningful work.

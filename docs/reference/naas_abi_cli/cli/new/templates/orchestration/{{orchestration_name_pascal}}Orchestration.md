# `{{orchestration_name_pascal}}Orchestration`

## What it is
A minimal Dagster-based orchestration template that subclasses `DagsterOrchestration` and provides a factory method to create an instance with empty Dagster `Definitions`.

## Public API
- `class {{orchestration_name_pascal}}Orchestration(DagsterOrchestration)`
  - `@classmethod New() -> "{{orchestration_name_pascal}}Orchestration"`
    - Creates and returns an orchestration instance configured with:
      - `dg.Definitions(assets=[], schedules=[], jobs=[], sensors=[])`

## Configuration/Dependencies
- Dependencies:
  - `dagster` imported as `dg`
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
- No runtime configuration is defined in this template; all Dagster components are initialized as empty lists.

## Usage
```python
from your_package.{{orchestration_name_pascal}}Orchestration import {{orchestration_name_pascal}}Orchestration

orch = {{orchestration_name_pascal}}Orchestration.New()
# orch is an instance of DagsterOrchestration with empty dg.Definitions
```

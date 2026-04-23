# `DemoOrchestration`

## What it is
A minimal `DagsterOrchestration` implementation that constructs an orchestration with an empty Dagster `Definitions` set (no assets, schedules, jobs, or sensors).

## Public API
- **Class `DemoOrchestration(DagsterOrchestration)`**
  - **`@classmethod New() -> DemoOrchestration`**
    - Creates and returns a `DemoOrchestration` instance configured with empty `dagster.Definitions`:
      - `assets=[]`
      - `schedules=[]`
      - `jobs=[]`
      - `sensors=[]`

## Configuration/Dependencies
- **Dependencies**
  - `dagster` (imported as `dg`)
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`

- **Configuration**
  - No external configuration is used; `New()` always builds empty `Definitions`.

## Usage
```python
from naas_abi.orchestrations.DemoOrchestration import DemoOrchestration

orch = DemoOrchestration.New()
```

## Caveats
- The created orchestration contains **no** assets, jobs, schedules, or sensors; it is effectively a placeholder scaffold.

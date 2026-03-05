# DemoOrchestration

## What it is
- A minimal `DagsterOrchestration` implementation that creates an empty Dagster `Definitions` object (no assets, jobs, schedules, or sensors).

## Public API
- `class DemoOrchestration(DagsterOrchestration)`
  - `@classmethod New() -> DemoOrchestration`
    - Returns a `DemoOrchestration` instance initialized with `dagster.Definitions` where:
      - `assets=[]`
      - `schedules=[]`
      - `jobs=[]`
      - `sensors=[]`

## Configuration/Dependencies
- **Dependencies**
  - `dagster` (imported as `dg`)
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`

## Usage
```python
from naas_abi.orchestrations.DemoOrchestration import DemoOrchestration

orch = DemoOrchestration.New()
# orch is a DagsterOrchestration with empty Dagster Definitions
```

## Caveats
- The orchestration contains **no** assets/jobs/schedules/sensors by default; running it will not execute any work unless extended.

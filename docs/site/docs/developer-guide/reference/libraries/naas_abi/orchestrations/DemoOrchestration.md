# `DemoOrchestration`

## What it is
A minimal `DagsterOrchestration` implementation that returns an orchestration with empty Dagster `Definitions` (no assets, jobs, schedules, or sensors). Dagster is imported lazily to allow module import without the Dagster extra installed.

## Public API
- **Class `DemoOrchestration(DagsterOrchestration)`**
  - Purpose: Provide an “empty” orchestration scaffold.
  - **`@classmethod New() -> DemoOrchestration`**
    - Creates a `DemoOrchestration` instance with:
      - `definitions=dagster.Definitions(assets=[], schedules=[], jobs=[], sensors=[])`
    - Raises a helpful “missing extra” error if `dagster` is not installed.

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
  - `naas_abi_core.utils.LegacyExtras.raise_missing_extra`
  - `dagster` (imported inside `New()`)

- **Configuration**
  - None; `New()` always builds empty `Definitions`.

## Usage
```python
from naas_abi.orchestrations.DemoOrchestration import DemoOrchestration

orch = DemoOrchestration.New()
```

## Caveats
- Produces an orchestration with **no** assets, jobs, schedules, or sensors (placeholder scaffold).
- Requires `dagster` to be installed at runtime when calling `New()`; otherwise it raises via `raise_missing_extra`.

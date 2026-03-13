# DagsterOrchestration

## What it is
- A small wrapper around Dagster’s `dagster.Definitions`, implementing/deriving from `naas_abi_core.orchestrations.Orchestrations`.
- Provides a stored `Definitions` object and a convenience constructor for an empty Dagster setup.

## Public API
- `class DagsterOrchestration(Orchestrations)`
  - `__init__(definitions: dagster.Definitions)`
    - Stores the provided Dagster `Definitions` instance.
  - `definitions -> dagster.Definitions` (property)
    - Returns the stored `Definitions`.
  - `New() -> DagsterOrchestration` (classmethod)
    - Returns a new instance initialized with `Definitions()` (empty definitions).

## Configuration/Dependencies
- **Dependencies**
  - `dagster.Definitions`
  - `naas_abi_core.orchestrations.Orchestrations.Orchestrations` (base class)

## Usage
```python
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration

orch = DagsterOrchestration.New()
defs = orch.definitions  # dagster.Definitions instance
print(defs)
```

## Caveats
- `New()` creates an empty `Definitions()`; jobs/assets/resources are not configured here.

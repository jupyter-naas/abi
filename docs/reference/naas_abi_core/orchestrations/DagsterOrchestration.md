# DagsterOrchestration

## What it is
A thin wrapper around Dagster’s `Definitions` object, implementing the `Orchestrations` interface/base type from `naas_abi_core`. It stores and exposes a `Definitions` instance and provides a convenience constructor for an empty definitions set.

## Public API
- **Class `DagsterOrchestration(Orchestrations)`**
  - **`__init__(definitions: dagster.Definitions)`**
    - Create an instance backed by the provided Dagster `Definitions`.
  - **Property `definitions -> dagster.Definitions`**
    - Returns the stored `Definitions` instance.
  - **Classmethod `New() -> DagsterOrchestration`**
    - Convenience constructor that returns a `DagsterOrchestration` initialized with `Definitions()`.

## Configuration/Dependencies
- **Dependencies**
  - `dagster.Definitions`
  - `naas_abi_core.orchestrations.Orchestrations.Orchestrations` (base class/interface)

## Usage
```python
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration

# Create an empty orchestration (no jobs/assets configured here)
orch = DagsterOrchestration.New()

# Access underlying Dagster Definitions
defs = orch.definitions
print(defs)
```

## Caveats
- `New()` creates `Definitions()` with no parameters; adding assets/jobs/etc. must be done by constructing `Definitions(...)` externally and passing it to `DagsterOrchestration(...)`.

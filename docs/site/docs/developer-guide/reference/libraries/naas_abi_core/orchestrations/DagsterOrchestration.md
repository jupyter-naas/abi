# DagsterOrchestration

> **Legacy.** Part of the `naas-abi-core[dagster]` / `[rabbitmq]` extras, for projects without NATS; removed in the next major. NATS projects use module jobs and the JetStream bus.

## What it is
- A small wrapper around Dagster’s `Definitions` that implements `naas_abi_core`’s `Orchestrations` base type.
- Designed to import even when Dagster is not installed; only `New()` (and the Dagster app) require the Dagster dependency.
- Marked as legacy (intended for removal in the next major release).

## Public API
- **Class `DagsterOrchestration(Orchestrations)`**
  - **`__init__(definitions: dagster.Definitions)`**
    - Stores the provided Dagster `Definitions` object.
  - **Property `definitions -> dagster.Definitions`**
    - Returns the stored `Definitions`.
  - **Classmethod `New() -> DagsterOrchestration`**
    - Imports `dagster.Definitions` and returns an instance initialized with `Definitions()`.
    - If Dagster is missing, raises via `raise_missing_extra(...)`.

## Configuration/Dependencies
- **Base type**
  - `naas_abi_core.orchestrations.Orchestrations.Orchestrations`
- **Optional dependency**
  - `dagster` (via the `naas-abi-core[dagster]` extra)
    - Required for `DagsterOrchestration.New()`
- **Utility**
  - `naas_abi_core.utils.LegacyExtras.raise_missing_extra` (used when Dagster is not installed)

## Usage
```python
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration

# Requires dagster to be installed (naas-abi-core[dagster])
orch = DagsterOrchestration.New()

# Access the underlying Dagster Definitions object
defs = orch.definitions
print(defs)
```

## Caveats
- `New()` requires Dagster; without it, it raises an error via `raise_missing_extra`.
- `New()` creates an empty `Definitions()`; to include assets/jobs/resources, construct a `Definitions(...)` externally and pass it to `DagsterOrchestration(...)`.
- Legacy path: intended for removal in the next major release.

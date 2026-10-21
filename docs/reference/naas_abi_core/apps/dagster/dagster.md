# dagster

> **Legacy.** Part of the `naas-abi-core[dagster]` / `[rabbitmq]` extras, for projects without NATS; removed in the next major. NATS projects use module jobs and the JetStream bus.

## What it is
- A legacy Dagster app module for `naas_abi_core` (intended for projects without NATS).
- On import, it boots the `Engine`, discovers `DagsterOrchestration` subclasses, optionally adds dataset compaction definitions, and exposes a merged Dagster `definitions` object.

## Public API
- **Module-level variable: `definitions`**
  - Type: `dagster.Definitions`
  - Purpose: the aggregated Dagster `Definitions` built from:
    - dataset compaction definitions (when applicable), plus
    - `.definitions` from each discovered `DagsterOrchestration` instance.
  - If nothing is discovered/added, it is an empty `Definitions()`.

## Configuration/Dependencies
- **Optional extra**
  - Requires the `naas-abi-core[dagster]` extra (otherwise import raises via `raise_missing_extra`).
- **Key dependencies**
  - `dagster.Definitions`
  - `naas_abi_core.engine.Engine.Engine`
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
  - `naas_abi_core.apps.dagster.DatasetCompaction.dataset_compaction_definitions`
- **Runtime behavior (import-time side effects)**
  - Instantiates `Engine()` and immediately calls `engine.load()`.
  - Conditionally adds dataset compaction definitions when:
    - `engine.services.dataset_available()` is `True`, and
    - `engine.hosts_jobs` is `False`
  - Iterates `engine.modules.values()` and each module’s `orchestrations`, collecting definitions from orchestrations that are subclasses of `DagsterOrchestration`.
  - Merges all collected definitions via `Definitions.merge(*all_definitions)`.

## Usage
Minimal Dagster entrypoint importing the exported `definitions`:

```python
# repository.py (or equivalent Dagster module)
from naas_abi_core.apps.dagster.dagster import definitions
```

## Caveats
- Importing this module triggers engine loading and orchestration discovery at import time.
- Dataset compaction definitions are added only when the dataset service is available and the engine is not hosting jobs (to avoid duplicate scheduling).
- Marked as legacy in the module docstring (“to be removed in the next major”).

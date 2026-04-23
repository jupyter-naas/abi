# dagster

## What it is
- A Dagster integration module that bootstraps the `naas_abi_core` `Engine`, discovers orchestrations that subclass `DagsterOrchestration`, collects their Dagster `Definitions`, and exposes a merged `definitions` object for Dagster to load.

## Public API
- **Module-level variable: `definitions`**
  - A `dagster.Definitions` instance.
  - Built by merging `Definitions` gathered from all discovered `DagsterOrchestration` subclasses.
  - If none are found, defaults to an empty `Definitions()`.

## Configuration/Dependencies
- **Dependencies**
  - `dagster.Definitions`
  - `naas_abi_core.engine.Engine.Engine`
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
- **Runtime behavior**
  - Instantiates `Engine()` and immediately calls `engine.load()` on import.
  - Iterates `engine.modules.values()` and each module’s `orchestrations` list to find subclasses of `DagsterOrchestration`.
  - For each match:
    - Calls `DagsterOrchestrationSubclass.New()` to create an instance.
    - Reads `.definitions` from the instance.
    - Merges all collected definitions via `Definitions.merge(*all_definitions)`.

## Usage
Minimal example (importing the `definitions` symbol that Dagster expects):

```python
# In your Dagster repository module (e.g., repository.py)
from naas_abi_core.apps.dagster.dagster import definitions
```

## Caveats
- Importing this module triggers `Engine.load()` and orchestration discovery at import time (side effects).
- Only orchestrations that are subclasses of `DagsterOrchestration` are included.
- If no qualifying orchestrations are discovered, `definitions` will be an empty `dagster.Definitions()`.

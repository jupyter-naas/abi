# dagster (Definitions loader/merger)

## What it is
A Dagster entrypoint module that:
- Instantiates and loads the `naas_abi_core` `Engine`
- Discovers orchestrations that subclass `DagsterOrchestration`
- Collects their Dagster `Definitions`
- Exposes a merged Dagster `definitions` object for Dagster to load

## Public API
- `definitions: dagster.Definitions`
  - The merged Dagster definitions from all discovered `DagsterOrchestration` subclasses.
  - If none are found, an empty `Definitions()` is provided.

## Configuration/Dependencies
- Depends on:
  - `dagster.Definitions`
  - `naas_abi_core.engine.Engine.Engine`
  - `naas_abi_core.orchestrations.DagsterOrchestration.DagsterOrchestration`
- Runtime behavior:
  - Creates `engine = Engine()` and calls `engine.load()`.
  - Iterates `engine.modules.values()` and then `module.orchestrations`.
  - For each orchestration class that is a subclass of `DagsterOrchestration`, it:
    - Instantiates via `DagsterOrchestrationSubclass.New()`
    - Reads `.definitions`
    - Merges all discovered definitions via `Definitions.merge(*all_definitions)`

## Usage
Use this module as the Dagster code location entrypoint (so Dagster can import `definitions`).

```python
# Example import path will depend on how this package is installed and exposed.
from naas_abi_core.apps.dagster.dagster import definitions

# 'definitions' is a dagster.Definitions instance ready for Dagster.
```

## Caveats
- Importing the module executes discovery immediately (`engine.load()` runs at import time).
- Only orchestrations that are subclasses of `DagsterOrchestration` are included.
- If no matching orchestrations are found, `definitions` is an empty `dagster.Definitions()`.

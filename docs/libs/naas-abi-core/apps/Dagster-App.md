# Dagster App

The Dagster app builds `Definitions` by scanning module orchestrations.

Related pages: [[Module-System]].

## How it works

- Starts engine and loads modules.
- Collects module orchestrations that subclass `DagsterOrchestration`.
- Calls `OrchestrationClass.New()` and merges returned `Definitions`.

## Entry module

- `naas_abi_core.apps.dagster.dagster`

If no orchestrations are found, an empty `Definitions()` is returned.

# Workspace

## What it is
`Workspace` is a thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.Workspace`, intended as an action class placeholder for workspace-related logic.

## Public API
- `class Workspace(_Workspace)`
  - Subclasses the base ontology `Workspace`.
  - `actions(self)`
    - Placeholder method for implementing workspace actions.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.ontologies.modules.NexusPlatformOntology.Workspace` (imported as `_Workspace`)

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.Workspace import Workspace

ws = Workspace()
ws.actions()  # no-op
```

## Caveats
- `actions()` is unimplemented and performs no operation.

# CurrentJobPosition

## What it is
- A thin subclass of `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.CurrentJobPosition`.
- Intended as a customization point for adding action logic via an `actions()` method.

## Public API
- `class CurrentJobPosition(_CurrentJobPosition)`
  - Inherits all behavior from the upstream `_CurrentJobPosition`.
  - `actions(self)`
    - Declared action hook.
    - **Not implemented** (method body is empty in the source).

## Configuration/Dependencies
- Imports and extends:
  - `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.CurrentJobPosition` (aliased as `_CurrentJobPosition`)

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.ontology.naas.ai.abi.linkedin.CurrentJobPosition import (
    CurrentJobPosition,
)

job_position = CurrentJobPosition()
job_position.actions()  # no behavior unless implemented in the base class or overridden
```

## Caveats
- `actions()` has no implementation in this subclass; override it to add functionality.
- Any required constructor arguments and inherited methods come from `_CurrentJobPosition`.

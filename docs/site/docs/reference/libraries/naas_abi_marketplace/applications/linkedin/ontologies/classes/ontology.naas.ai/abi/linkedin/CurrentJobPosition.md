# CurrentJobPosition

## What it is
- A thin subclass wrapper around `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.CurrentJobPosition`.
- Provides an `actions()` method stub intended to be implemented with custom logic.

## Public API
- `class CurrentJobPosition(_CurrentJobPosition)`
  - Subclasses the imported base `CurrentJobPosition`.
  - `actions(self)`
    - Placeholder action method.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.CurrentJobPosition` (imported as `_CurrentJobPosition`)

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.ontology.naas.ai.abi.linkedin.CurrentJobPosition import (
    CurrentJobPosition,
)

job_position = CurrentJobPosition()
job_position.actions()  # no-op unless overridden
```

## Caveats
- `actions()` is a no-op and must be implemented/overridden to perform any work.
- Instantiation requirements (constructor args, inherited behavior) are defined by the upstream `_CurrentJobPosition` class.

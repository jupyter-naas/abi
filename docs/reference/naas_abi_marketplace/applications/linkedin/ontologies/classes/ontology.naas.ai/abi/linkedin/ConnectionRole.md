# ConnectionRole

## What it is
- A thin subclass of the upstream LinkedIn ontology class `ConnectionRole`.
- Provides an `actions()` hook method intended for custom logic.

## Public API
- `class ConnectionRole(_ConnectionRole)`
  - Inherits from `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.ConnectionRole`.
  - `actions(self)`
    - Hook for implementing action logic.
    - **No implementation in this file** (method body is empty).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.ConnectionRole` (imported as `_ConnectionRole`)

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.ontology.naas.ai.abi.linkedin.ConnectionRole import (
    ConnectionRole,
)

role = ConnectionRole()
role.actions()  # implement in subclass or edit method to do something
```

## Caveats
- `actions()` is not implemented in this module; calling it will not execute any custom logic unless you add it.
- Constructor/signature and behavior come entirely from the upstream `_ConnectionRole` class.

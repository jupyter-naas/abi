# NewbornDisposition

## What it is
- A thin subclass wrapper around `NewbornDisposition` from the `BirthRegistrationProcess` ontology process module.
- Exposes an `actions()` hook method intended for custom implementation.

## Public API
- `class NewbornDisposition(_NewbornDisposition)`
  - Inherits from `naas_abi_marketplace.domains.personnel.ontologies.processes.BirthRegistrationProcess.NewbornDisposition`.
  - `actions(self)`
    - Hook for action logic.
    - Declared but **not implemented** (empty method body).

## Configuration/Dependencies
- Imports and subclasses:
  - `naas_abi_marketplace.domains.personnel.ontologies.processes.BirthRegistrationProcess.NewbornDisposition` (aliased as `_NewbornDisposition`)

## Usage
```python
from naas_abi_marketplace.domains.personnel.ontologies.classes.commoncoreontologies_org.NewbornDisposition import (
    NewbornDisposition,
)

nd = NewbornDisposition()
nd.actions()  # no-op unless implemented in a subclass/parent
```

## Caveats
- `actions()` has no implementation in this module; calling it will do nothing unless behavior exists in the parent class or you override it.

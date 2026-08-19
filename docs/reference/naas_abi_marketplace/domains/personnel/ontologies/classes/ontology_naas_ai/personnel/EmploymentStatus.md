# EmploymentStatus

## What it is
- A thin subclass of `EmploymentStatus` from `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology`.
- Provides a customization point (“action class”) for extending `EmploymentStatus`.

## Public API
- `class EmploymentStatus(_EmploymentStatus)`
  - Inherits all behavior from `_EmploymentStatus`.
  - `actions(self)`
    - Placeholder method for custom logic.
    - No implementation in this file (implicitly returns `None`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.EmploymentStatus` (imported as `_EmploymentStatus`)

## Usage
```python
from naas_abi_marketplace.domains.personnel.ontologies.classes.ontology_demo.personnel.EmploymentStatus import (
    EmploymentStatus,
)

status = EmploymentStatus()

# Placeholder method: currently does nothing and returns None.
print(status.actions())  # None
```

## Caveats
- `actions()` is not implemented; calling it performs no action and returns `None`.
- Any constructor requirements, properties, or methods are inherited from `_EmploymentStatus` and are not defined in this file.

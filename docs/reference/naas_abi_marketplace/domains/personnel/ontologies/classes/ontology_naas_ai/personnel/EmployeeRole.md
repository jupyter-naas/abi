# EmployeeRole

## What it is
- A thin subclass of `PersonnelOntology.EmployeeRole`, provided as an extension point to add domain-specific logic for an employee role.

## Public API
- `class EmployeeRole(_EmployeeRole)`
  - Inherits all behavior from `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.EmployeeRole`.
  - `actions(self)`
    - Placeholder method intended for custom action logic.
    - Contains only a docstring (no executable code); returns `None`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.EmployeeRole` (imported as `_EmployeeRole`).

## Usage
```python
from naas_abi_marketplace.domains.personnel.ontologies.classes.ontology_demo.personnel.EmployeeRole import EmployeeRole

role = EmployeeRole()
print(role.actions())  # None (no logic implemented)
```

## Caveats
- `actions()` is not implemented; calling it has no effect and returns `None` unless overridden.
- Any usable attributes/methods are defined on the inherited `_EmployeeRole` class (not shown in this file).

# EmploymentRecord

## What it is
- A thin subclass of `PersonnelOntology.EmploymentRecord` intended as an extension point for adding action logic related to an employment record.
- Defines an `actions()` method stub with no implementation.

## Public API
- **Class `EmploymentRecord(_EmploymentRecord)`**
  - Inherits from `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.EmploymentRecord`.
  - **Method `actions(self)`**
    - Placeholder method for action logic.
    - No behavior is implemented in this file.

## Configuration/Dependencies
- Imports and depends on:
  - `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.EmploymentRecord` (aliased as `_EmploymentRecord`)

## Usage
```python
from naas_abi_marketplace.domains.personnel.ontologies.classes.ontology_demo.personnel.EmploymentRecord import (
    EmploymentRecord,
)

record = EmploymentRecord()
record.actions()  # stub: no implementation in this class
```

## Caveats
- `actions()` has no body; calling it will do nothing unless overridden or the base class provides behavior elsewhere.

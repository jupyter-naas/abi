# JobDescription

## What it is
- A thin subclass of `PersonnelOntology.JobDescription`.
- Provides an extension point (`actions()`) for adding custom logic.

## Public API
- `class JobDescription(_JobDescription)`
  - Inherits all behavior from `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.JobDescription`.
  - `actions(self)`
    - Placeholder method intended for custom action logic.
    - Currently contains only a docstring (no implementation, no return).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.JobDescription` (imported as `_JobDescription`).

## Usage
```python
from naas_abi_marketplace.domains.personnel.ontologies.classes.ontology_demo.personnel.JobDescription import (
    JobDescription,
)

jd = JobDescription()
jd.actions()  # no-op: method is not implemented
```

## Caveats
- `actions()` is empty; override/extend it to perform any work.

# JobPosition

## What it is
A thin subclass of the ontology-defined `JobPosition` intended as an extension point for adding custom action logic.

## Public API
- `class JobPosition(_JobPosition)`
  - Inherits from: `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.JobPosition`
  - `actions(self)`
    - Placeholder method for implementing custom logic (currently no behavior).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology.JobPosition`

## Usage
```python
from naas_abi_marketplace.domains.personnel.ontologies.classes.ontology_demo.personnel.JobPosition import JobPosition

job_position = JobPosition()
job_position.actions()  # no-op placeholder
```

## Caveats
- `actions()` is not implemented (method body contains only a docstring). Override it to add behavior.

# OntologyClassRole

## What it is
A thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.OntologyClassRole` that provides an overridable `actions()` hook. As shipped, it contains no custom logic.

## Public API
- `class OntologyClassRole(_OntologyClassRole)`
  - Inherits all behavior from the upstream `_OntologyClassRole`.
  - `actions(self) -> None`
    - Placeholder method intended for implementing custom action logic.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.ontologies.modules.NexusPlatformOntology.OntologyClassRole` (imported as `_OntologyClassRole`)

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.OntologyClassRole import OntologyClassRole

role = OntologyClassRole()
role.actions()  # no-op by default
```

## Caveats
- `actions()` is a no-op; subclass or modify it to add behavior.
- Instantiation requirements (constructor args, side effects) are defined by the upstream `_OntologyClassRole` base class.

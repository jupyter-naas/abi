# OntologyObjectProperty

## What it is
A thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.OntologyObjectProperty` intended as an extension point for adding custom action logic.

## Public API
- `class OntologyObjectProperty(_OntologyObjectProperty)`
  - Inherits all behavior from `_OntologyObjectProperty`.
  - `actions(self)`
    - Placeholder method meant to be overridden/implemented.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.ontologies.modules.NexusPlatformOntology.OntologyObjectProperty` (imported as `_OntologyObjectProperty`)

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.OntologyObjectProperty import (
    OntologyObjectProperty,
)

obj = OntologyObjectProperty()
obj.actions()  # no-op by default
```

## Caveats
- `actions()` is a no-op placeholder; it must be implemented to have any effect.

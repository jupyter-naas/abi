# GlobalHeadquarters

## What it is
- A thin subclass wrapper around `naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.modules.OrganizationOntology.GlobalHeadquarters`.
- Provides an override point for defining custom actions via an `actions()` method.

## Public API
- `class GlobalHeadquarters(_GlobalHeadquarters)`
  - Inherits all behavior from `_GlobalHeadquarters`.
  - `actions(self)`
    - Placeholder method intended for custom logic.
    - Currently contains only a docstring and no implementation.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.intelligence.ontologies.organizations.ontologies.modules.OrganizationOntology.GlobalHeadquarters` (imported as `_GlobalHeadquarters`).

## Usage
```python
from naas_abi_marketplace.domains.intelligence.ontologies.classes.ontology_demo.abi.GlobalHeadquarters import (
    GlobalHeadquarters,
)

ghq = GlobalHeadquarters()

# Override point: implement actions() in this subclass to add behavior.
ghq.actions()
```

## Caveats
- `actions()` is effectively a no-op placeholder; calling it will not perform any work unless implemented.

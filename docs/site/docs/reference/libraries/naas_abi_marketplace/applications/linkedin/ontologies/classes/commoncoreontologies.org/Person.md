# Person

## What it is
- A thin subclass of `ActOfConnectionsOnLinkedIn.Person` intended to represent an action-oriented `Person` within the LinkedIn ontology integration.
- Provides an `actions()` hook for custom logic (currently unimplemented).

## Public API
- `class Person(_Person)`
  - Inherits from `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.Person`.
  - `actions(self)`
    - Placeholder method for implementing action logic.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.Person` (imported as `_Person`).

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.commoncoreontologies.org.Person import Person

p = Person()
p.actions()  # currently no-op
```

## Caveats
- `actions()` is a stub and contains no implementation; calling it has no effect.

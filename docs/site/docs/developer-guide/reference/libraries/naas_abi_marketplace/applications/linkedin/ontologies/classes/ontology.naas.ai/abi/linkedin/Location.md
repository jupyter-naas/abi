# Location

## What it is
- A thin subclass wrapper around `ActOfConnectionsOnLinkedIn.Location`.
- Provides an `actions()` hook intended to be overridden with custom logic.

## Public API
- `class Location(_Location)`
  - Extends: `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.Location`
  - `actions(self)`
    - Placeholder method; currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.Location` (imported as `_Location`).
- No configuration in this file.

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.ontology.naas.ai.abi.linkedin.Location import Location

loc = Location()
loc.actions()  # no-op
```

## Caveats
- `actions()` is unimplemented in this class; calling it has no effect unless you override it in a subclass.

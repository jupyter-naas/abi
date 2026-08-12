# Location

## What it is
- A thin subclass of `ActOfConnectionsOnLinkedIn.Location`.
- Intended as an extension point where you can implement custom logic in `actions()`.

## Public API
- `class Location(_Location)`
  - Extends: `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.Location`
  - `actions(self)`
    - Stub method (no implementation in this file). Intended to be filled in with custom logic.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.Location` (imported as `_Location`)
- No configuration is defined in this module.

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.ontology.naas.ai.abi.linkedin.Location import Location

loc = Location()
loc.actions()  # currently does nothing (no implementation)
```

## Caveats
- `actions()` has no body in the source file; calling it will not perform any action unless implemented (e.g., by editing this method or overriding it in a subclass).

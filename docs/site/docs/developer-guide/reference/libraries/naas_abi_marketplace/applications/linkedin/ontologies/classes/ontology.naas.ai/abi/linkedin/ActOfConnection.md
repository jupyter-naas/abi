# ActOfConnection

## What it is
- A thin subclass wrapper around `ActOfConnection` imported from `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn`.
- Intended as a place to implement/override action logic for the “ActOfConnection” concept.

## Public API
- `class ActOfConnection(_ActOfConnection)`
  - Inherits all behavior from the imported base class.
  - `actions(self)`
    - Placeholder method meant to be implemented.
    - Current implementation: no-op (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.ActOfConnection` (imported as `_ActOfConnection`)

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.ontology.naas.ai.abi.linkedin.ActOfConnection import (
    ActOfConnection,
)

class MyConnectionAction(ActOfConnection):
    def actions(self):
        # implement your logic here
        return "done"

obj = MyConnectionAction()
print(obj.actions())
```

## Caveats
- `actions()` in this module does nothing unless you override/implement it.
- Actual initialization requirements and behavior are defined in the imported base class (`_ActOfConnection`).

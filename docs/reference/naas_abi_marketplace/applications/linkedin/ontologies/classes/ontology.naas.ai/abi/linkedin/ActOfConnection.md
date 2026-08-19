# ActOfConnection

## What it is
- A thin subclass of `ActOfConnection` imported from `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn`.
- Provides a local extension point for implementing action logic via `actions()`.

## Public API
- `class ActOfConnection(_ActOfConnection)`
  - Inherits all behavior from the imported base class.
  - `actions(self)`
    - Stub method intended to be implemented/overridden in this subclass.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn.ActOfConnection` (imported as `_ActOfConnection`)

## Usage
```python
from naas_abi_marketplace.applications.linkedin.ontologies.classes.ontology.naas.ai.abi.linkedin.ActOfConnection import (
    ActOfConnection,
)

class MyActOfConnection(ActOfConnection):
    def actions(self):
        return "implemented"

obj = MyActOfConnection()
print(obj.actions())
```

## Caveats
- `actions()` has no implementation in this module; calling it without overriding will not perform any action.
- Construction/required parameters and runtime behavior are defined by the base class (`_ActOfConnection`).

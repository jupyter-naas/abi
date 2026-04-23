# Message

## What it is
- A thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.Message`.
- Intended as an action/extension point for Message-related logic.

## Public API
- `class Message(_Message)`
  - Inherits all behavior from `_Message` (aliased import).
  - `actions(self)`
    - Placeholder method for implementing custom logic.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on `naas_abi.ontologies.modules.NexusPlatformOntology`:
  - `Message` is imported and aliased as `_Message`.

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.Message import Message

msg = Message()
msg.actions()  # currently no-op
```

## Caveats
- `actions()` is a no-op and must be implemented to provide any behavior.
- Actual capabilities and required initialization parameters are defined by the base class `_Message`.

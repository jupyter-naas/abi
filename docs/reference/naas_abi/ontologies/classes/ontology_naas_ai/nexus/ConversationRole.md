# ConversationRole

## What it is
- A thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.ConversationRole`.
- Provides an override point (`actions`) for implementing custom logic.

## Public API
- `class ConversationRole(_ConversationRole)`
  - Inherits all behavior from `_ConversationRole`.
  - `actions(self)`
    - Placeholder method intended for custom action logic.
    - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.ontologies.modules.NexusPlatformOntology.ConversationRole` (imported as `_ConversationRole`)

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.ConversationRole import ConversationRole

role = ConversationRole()
role.actions()  # no-op by default
```

## Caveats
- `actions()` is not implemented; calling it has no effect unless overridden/extended.

# Conversation

## What it is
- A thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.Conversation`.
- Intended as an extension point for implementing custom conversation-related actions.

## Public API
- `class Conversation(_Conversation)`
  - `actions(self)`
    - Placeholder method meant to be overridden/implemented with custom logic.
    - Current implementation: `pass` (no behavior).

## Configuration/Dependencies
- Depends on `naas_abi.ontologies.modules.NexusPlatformOntology.Conversation` (imported as `_Conversation`).

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.Conversation import Conversation

class MyConversation(Conversation):
    def actions(self):
        # implement your logic here
        return "ok"

c = MyConversation()
print(c.actions())
```

## Caveats
- `actions()` does nothing unless you override/implement it.
- Behavior and required initialization parameters (if any) are defined by the parent class `_Conversation`.

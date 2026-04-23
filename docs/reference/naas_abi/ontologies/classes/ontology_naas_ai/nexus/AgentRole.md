# AgentRole

## What it is
- A thin subclass of `naas_abi.ontologies.modules.NexusPlatformOntology.AgentRole`.
- Provides an overridable `actions()` hook intended for custom logic.

## Public API
- `class AgentRole(_AgentRole)`
  - Extends the ontology-provided `AgentRole`.
- `AgentRole.actions(self)`
  - Placeholder method for implementing role-specific actions.
  - Currently does nothing (`pass`).

## Configuration/Dependencies
- Depends on: `naas_abi.ontologies.modules.NexusPlatformOntology.AgentRole` (imported as `_AgentRole`).

## Usage
```python
from naas_abi.ontologies.classes.ontology_naas_ai.nexus.AgentRole import AgentRole

class MyAgentRole(AgentRole):
    def actions(self):
        print("Running custom actions")

role = MyAgentRole()
role.actions()
```

## Caveats
- `actions()` is not implemented in this file; calling it on `AgentRole` as-is will have no effect.

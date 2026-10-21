# InsideSalesRepresentativeAgent

## What it is
A **non-functional template** for an “Inside Sales Representative” domain-expert agent. The module defines metadata/constants and stubs for agent creation and an agent class, but does not implement any runtime behavior.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Logs a warning that the agent is not functional and returns `None`.
- `class InsideSalesRepresentativeAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent` with no additional implementation.

### Module constants (metadata)
- `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
- `MODEL`, `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
- `SUGGESTIONS` (list of label/value prompt templates)

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent` (`IntentAgent`, `AgentConfiguration`, `AgentSharedState`)
- Configuration inputs (currently unused due to non-functional implementation):
  - `agent_shared_state: Optional[AgentSharedState]`
  - `agent_configuration: Optional[AgentConfiguration]`

## Usage
```python
from naas_abi_marketplace.domains.inside-sales_representative.agents.InsideSalesRepresentativeAgent import create_agent

agent = create_agent()
assert agent is None  # template only; returns None
```

## Caveats
- The module explicitly states **“NOT FUNCTIONAL YET”**:
  - `create_agent()` always returns `None`.
  - `InsideSalesRepresentativeAgent` contains only `pass` and provides no behavior.

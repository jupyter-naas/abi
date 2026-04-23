# DataGouvAgent

## What it is
- An `IntentAgent` wrapper configured to provide **general guidance** about DataGouv (French open data platform) and dataset discovery.
- Ships with **no tools** configured; it cannot fetch datasets or perform actions.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `DataGouvAgent`.
  - Sets:
    - `name`: `"DataGouv"`
    - `description`: guidance-focused description
    - `system_prompt`: constraints and operating guidelines
    - `tools`: empty list
    - `intents`: two RAW intents (feature info; open data/dataset discovery)
    - `state`: provided or new `AgentSharedState`
    - `configuration`: provided or new `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
    - `memory`: `None`

- `class DataGouvAgent(IntentAgent)`
  - Concrete agent type; does not add behavior beyond `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Chat model dependency:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model` (used as `model.model`)
- Agent constants:
  - `NAME`, `DESCRIPTION`, `SYSTEM_PROMPT`, `SUGGESTIONS` (empty list)

## Usage
```python
from naas_abi_marketplace.applications.datagouv.agents.DataGouvAgent import create_agent

agent = create_agent()

# Use `agent` with your host framework's execution/chat loop for IntentAgent instances.
# Note: no tools are configured, so it will only provide general guidance.
```

## Caveats
- No DataGouv tools are configured (`tools = []`), so the agent:
  - cannot retrieve datasets,
  - cannot perform external actions,
  - can only provide general information and guidance per `SYSTEM_PROMPT`.

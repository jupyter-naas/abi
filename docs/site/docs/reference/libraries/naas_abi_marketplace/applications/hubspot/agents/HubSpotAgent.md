# HubSpotAgent

## What it is
A minimal `IntentAgent` implementation configured to provide general guidance about HubSpot (CRM, marketing, sales) **without any connected HubSpot tools**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `HubSpotAgent`.
  - Sets:
    - `name`: `"HubSpot"`
    - `description`: guidance-focused description
    - `system_prompt`: predefined HubSpot guidance prompt
    - `tools`: empty list (`[]`)
    - `intents`: two predefined raw intents (informational responses)
    - `state`: provided `AgentSharedState` or a new instance
    - `configuration`: provided `AgentConfiguration` or default with `system_prompt`
    - `memory`: `None`

- `class HubSpotAgent(IntentAgent)`
  - Concrete agent class; no additional methods/overrides (inherits all behavior from `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Chat model is imported inside `create_agent`:
  - `from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model`
  - Passed as `chat_model=model.model`
- Tools:
  - None configured (`tools = []`)

## Usage
```python
from naas_abi_marketplace.applications.hubspot.agents.HubSpotAgent import create_agent

agent = create_agent()
# Use `agent` via the APIs provided by IntentAgent in your runtime/framework.
```

## Caveats
- No HubSpot integrations/tools are configured; the agent is limited to general information and guidance.
- The intent targets are static text responses and do not access CRM data.

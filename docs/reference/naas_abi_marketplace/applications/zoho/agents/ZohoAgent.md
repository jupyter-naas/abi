# ZohoAgent

## What it is
A lightweight `IntentAgent` configuration for providing general guidance about Zoho (CRM, business apps, productivity tools). It defines a system prompt and a couple of pre-set intents, but **does not include any Zoho tools or live data access**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `ZohoAgent`.
  - Sets:
    - `name`: `"Zoho"`
    - `description`: guidance-focused description
    - `system_prompt`: emphasizes no tool access and guidance-only behavior
    - `tools`: empty list (`[]`)
    - `intents`: two `IntentType.RAW` intents with canned guidance text
    - `state`: provided `AgentSharedState` or a new one
    - `configuration`: provided `AgentConfiguration` or a new one using `SYSTEM_PROMPT`
    - `memory`: `None`

- `class ZohoAgent(IntentAgent)`
  - Concrete agent class with no additional behavior beyond `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Uses the chat model imported at runtime from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model`
- Constants:
  - `NAME`, `DESCRIPTION`, `SYSTEM_PROMPT`
  - `SUGGESTIONS` is defined but empty and unused.

## Usage
```python
from naas_abi_marketplace.applications.zoho.agents.ZohoAgent import create_agent

agent = create_agent()
# The returned agent has no tools configured; it is intended for general guidance.
```

## Caveats
- No Zoho tooling is configured (`tools = []`), so the agent cannot access Zoho accounts, data, or perform actions—only provide general information based on its prompt/intents.

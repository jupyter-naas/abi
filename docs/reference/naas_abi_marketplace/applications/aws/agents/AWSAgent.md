# AWSAgent

## What it is
- A thin `IntentAgent` specialization for answering general AWS questions.
- Ships with:
  - A fixed system prompt emphasizing **no AWS tool access** (guidance only).
  - A couple of predefined RAW intents.
  - No tools configured (`tools = []`).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that constructs and returns an `AWSAgent` with defaults:
    - `name="AWS"`, `description=...`
    - `chat_model` from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`
    - `intents` (RAW) for AWS info and infrastructure/resource management
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided
    - `AgentSharedState()` if not provided
    - `tools=[]`, `memory=None`

- `class AWSAgent(IntentAgent)`
  - Marker subclass of `IntentAgent` (no additional methods/overrides).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Depends on chat model module:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (uses `model.model`)
- Configuration inputs:
  - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` controls the agent’s operating constraints (guidance only, no actions).

## Usage
```python
from naas_abi_marketplace.applications.aws.agents.AWSAgent import create_agent

agent = create_agent()

# Interact with the agent using your IntentAgent runtime/orchestrator.
# (This module only provides the agent factory and definition.)
```

## Caveats
- No AWS tools are configured (`tools=[]`), so the agent cannot access or modify AWS resources; it only provides general guidance.

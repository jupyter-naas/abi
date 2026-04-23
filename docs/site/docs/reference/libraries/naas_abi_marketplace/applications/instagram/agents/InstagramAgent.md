# InstagramAgent

## What it is
An `IntentAgent` implementation for Instagram-related guidance (features, content management, engagement). This agent is configured **without any Instagram tools**, so it only returns general information via predefined intents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns an `InstagramAgent` with:
    - Name/description constants
    - A system prompt describing constraints (no tool access)
    - No tools (`tools = []`)
    - Two predefined RAW intents for general Instagram guidance
    - A ChatGPT model from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`
- `class InstagramAgent(IntentAgent)`
  - Concrete agent class; no additional behavior beyond `IntentAgent` (inherits all functionality).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (imports `model`, uses `model.model` as `chat_model`)
- Configuration:
  - If `agent_configuration` is not provided, `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` is used.
  - If `agent_shared_state` is not provided, a new `AgentSharedState()` is created.
- Tools:
  - None configured (`tools = []`)

## Usage
```python
from naas_abi_marketplace.applications.instagram.agents.InstagramAgent import create_agent

agent = create_agent()
print(agent.name)          # "Instagram"
print(agent.description)   # Helps you interact with Instagram...
```

## Caveats
- No Instagram tool integration is provided in this file (`tools` is empty).
- The system prompt explicitly constrains the agent to **general information and guidance only**; it should not perform Instagram actions or access account/content.

# `{{agent_name_pascal}}Agent`

## What it is
- A template agent class that subclasses `naas_abi_core.services.agent.Agent.Agent`.
- Provides a single factory method (`New`) to create a configured agent instance using a ChatGPT model.

## Public API
- **Constants**
  - `NAME`: Agent name (`"{{agent_name_pascal}}Agent"`).
  - `DESCRIPTION`: Human-readable description.
  - `SYSTEM_PROMPT`: Default system prompt used when no configuration is provided.
- **Class `{{agent_name_pascal}}Agent(Agent)`**
  - `@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> "{{agent_name_pascal}}Agent"`
    - Creates and returns a new agent instance.
    - Behavior:
      - Imports the ChatGPT model from `naas_abi_marketplace.ai.chatgpt.models.gpt_5` and uses `chatgpt_model.model`.
      - If `agent_configuration` is not provided, builds `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`.
      - If `agent_shared_state` is not provided, builds a new `AgentSharedState()`.
      - Creates the agent with empty `tools` and `agents`, and `memory=None`.

## Configuration/Dependencies
- **Depends on**
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_5`:
    - `model` (used as the agent chat model)
- **Configuration**
  - `AgentConfiguration` can be passed in; otherwise a default is created with `system_prompt=SYSTEM_PROMPT`.

## Usage
```python
# Assuming the templated class has been generated with a real name, e.g. MyAgent
from my_package.MyAgent import MyAgent  # adjust import to your project layout

agent = MyAgent.New()
```

With explicit configuration/state:
```python
from naas_abi_core.services.agent.Agent import AgentConfiguration, AgentSharedState
from my_package.MyAgent import MyAgent  # adjust import

state = AgentSharedState()
config = AgentConfiguration(system_prompt="You are a custom agent.")

agent = MyAgent.New(agent_shared_state=state, agent_configuration=config)
```

## Caveats
- `tools` and `agents` are always initialized as empty lists in `New`; this template does not register any tools/sub-agents by default.
- `memory` is set to `None` by default.

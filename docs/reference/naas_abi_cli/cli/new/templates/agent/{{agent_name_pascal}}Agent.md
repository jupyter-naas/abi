# `{{agent_name_pascal}}Agent`

## What it is
- A template `Agent` implementation that instantiates an agent with:
  - A default system prompt (`SYSTEM_PROMPT`)
  - A ChatGPT-based chat model (`gpt_5`)
  - Empty `tools` and `agents` lists
  - Optional shared state and configuration

## Public API
- `class {{agent_name_pascal}}Agent(Agent)`
  - `@classmethod New(cls, agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> "{{agent_name_pascal}}Agent"`
    - Factory method to create and return a configured agent instance.
    - Behavior:
      - Imports `naas_abi_marketplace.ai.chatgpt.models.gpt_5.model` and uses `chatgpt_model.model` as `chat_model`.
      - If `agent_configuration` is not provided, creates `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`.
      - If `agent_shared_state` is not provided, creates a new `AgentSharedState()`.
      - Constructs the agent with:
        - `name=NAME`
        - `description=DESCRIPTION`
        - `tools=[]`
        - `agents=[]`
        - `memory=None`
        - `state=agent_shared_state`
        - `configuration=agent_configuration`

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.Agent`:
  - `Agent`
  - `AgentConfiguration`
  - `AgentSharedState`
- Uses ChatGPT model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_5`
- Configuration constants:
  - `NAME = "{{agent_name_pascal}}Agent"`
  - `DESCRIPTION = "An helpful agent that can help you with your tasks."`
  - `SYSTEM_PROMPT` (multiline string: `"You are {{agent_name_pascal}}Agent."`)

## Usage
```python
from naas_abi_cli.cli.new.templates.agent.{{agent_name_pascal}}Agent import {{agent_name_pascal}}Agent

agent = {{agent_name_pascal}}Agent.New()
print(agent)
```

## Caveats
- `tools` and `agents` are initialized as empty lists; no tool/agent capabilities are added by default.
- `memory` is explicitly set to `None`.
- Requires the `gpt_5` model module import to be available at runtime.

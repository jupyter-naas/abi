# SlackAgent

## What it is
- A minimal **Slack-focused** `IntentAgent` definition.
- Provides **general guidance** about Slack features and channel/message management.
- **Does not include Slack tools** (no real Slack actions are performed).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that constructs and returns a configured `SlackAgent`.
  - Sets:
    - `name`: `"Slack"`
    - `description`: Slack guidance description
    - `system_prompt`: constraints + guidance-oriented prompt (no tool access)
    - `tools`: `[]` (empty)
    - `intents`: two RAW intents with canned guidance targets
    - `state`: provided or new `AgentSharedState()`
    - `configuration`: provided or `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
    - `memory`: `None`

- `class SlackAgent(IntentAgent)`
  - No additional methods/overrides; inherits behavior from `IntentAgent`.

## Configuration/Dependencies
- Depends on core agent types from `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Uses a chat model imported from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (as `model.model`)
- Agent constants:
  - `SYSTEM_PROMPT`: explicitly states **no Slack tool access**, guidance-only behavior.
  - `SUGGESTIONS`: empty list.

## Usage
```python
from naas_abi_marketplace.applications.slack.agents.SlackAgent import create_agent

agent = create_agent()
# Use `agent` per the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No Slack API/tools are configured (`tools = []`).
- The agent should only provide **general Slack information** and must not claim to read or manage real channels/messages.

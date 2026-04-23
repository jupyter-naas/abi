# TwilioAgent

## What it is
- An `IntentAgent` implementation that provides **general guidance** about Twilio (SMS, voice, messaging).
- Ships **without Twilio tools** configured; it does not send messages or place calls.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that constructs and returns a configured `TwilioAgent`.
  - Sets:
    - `name`: `"Twilio"`
    - `description`: Twilio-focused helper text
    - `system_prompt`: constraints and operating guidelines (no tools)
    - `tools`: empty list
    - `intents`: two RAW intents providing informational responses
    - `state`: provided or new `AgentSharedState`
    - `memory`: `None`
- `class TwilioAgent(IntentAgent)`
  - Concrete agent type; no additional methods beyond `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Uses chat model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (`model.model`)
- Configuration points:
  - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if none provided.
  - `AgentSharedState()` if none provided.

## Usage
```python
from naas_abi_marketplace.applications.twilio.agents.TwilioAgent import create_agent

agent = create_agent()

# Use the returned IntentAgent according to your framework's execution/run method.
# (This module only provides the agent construction and configuration.)
print(agent.name)  # "Twilio"
```

## Caveats
- No Twilio tools are configured (`tools = []`), so the agent:
  - cannot send SMS, make calls, or perform Twilio operations
  - only provides general information and guidance per `SYSTEM_PROMPT` constraints

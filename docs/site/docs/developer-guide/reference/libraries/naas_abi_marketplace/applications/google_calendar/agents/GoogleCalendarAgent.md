# GoogleCalendarAgent

## What it is
A minimal `IntentAgent` implementation configured to provide general guidance about Google Calendar (features, scheduling, event management) **without** any connected Google Calendar tools or API access.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `GoogleCalendarAgent`.
  - Sets:
    - `system_prompt` (if not provided) to `SYSTEM_PROMPT`
    - empty `tools` list (no integrations)
    - two RAW `Intent` entries for informational responses
    - `chat_model` from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`
    - `memory=None`
- `class GoogleCalendarAgent(IntentAgent)`
  - No additional methods/overrides; inherits behavior from `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Chat model dependency:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (imports `model` and uses `model.model`)
- Key module constants:
  - `NAME = "Google_Calendar"`
  - `DESCRIPTION = "Helps you interact with Google Calendar for scheduling and event management."`
  - `SYSTEM_PROMPT` describes no-tool constraints and guidance-only behavior
  - `SUGGESTIONS: list = []`

## Usage
```python
from naas_abi_marketplace.applications.google_calendar.agents.GoogleCalendarAgent import create_agent

agent = create_agent()
# Interactions depend on the underlying IntentAgent interface.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot access calendars or perform actions; it can only provide general information and guidance.
- The concrete runtime interaction methods come from `IntentAgent` (not defined in this file).

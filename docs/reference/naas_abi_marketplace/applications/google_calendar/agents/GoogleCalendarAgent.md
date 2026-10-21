# GoogleCalendarAgent

## What it is
An `IntentAgent` implementation that provides **general guidance** about Google Calendar (features, scheduling, event management). It has **no tools/integrations configured**, so it cannot access or modify any real calendar data.

## Public API
- `class GoogleCalendarAgent(IntentAgent)`
  - Agent class with preset metadata:
    - `name = "Google_Calendar"`
    - `description = "Helps you interact with Google Calendar for scheduling and event management."`
    - `system_prompt` describing guidance-only behavior (no tool access)
    - `suggestions = []`
- `GoogleCalendarAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GoogleCalendarAgent`
  - Factory constructor that:
    - Gets default chat and embedding models via the application `ABIModule` model registry.
    - Configures:
      - `tools = []`
      - two `IntentType.RAW` intents for informational responses
      - `memory = None`
    - Defaults if not provided:
      - `agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)`
      - `agent_shared_state = AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on application module singleton:
  - `from naas_abi_marketplace.applications.google_calendar import ABIModule`
  - Requires `ABIModule.get_instance().engine.services.model_registry` to be initialized.
- Model dependencies (resolved via registry):
  - `registry.get_default_chat_model()`
  - `registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.google_calendar.agents.GoogleCalendarAgent import GoogleCalendarAgent

agent = GoogleCalendarAgent.New()
# Interact with `agent` using the interfaces provided by IntentAgent in naas_abi_core.
```

## Caveats
- No tools are configured (`tools = []`): the agent cannot read/write calendars or perform operations, only explain concepts and best practices.
- `New()` asserts that the model registry is initialized; it will raise an assertion error if not.

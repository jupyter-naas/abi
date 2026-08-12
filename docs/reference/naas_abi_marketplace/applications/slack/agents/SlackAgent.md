# SlackAgent

## What it is
- A Slack-focused `IntentAgent` that provides **general information and guidance** about Slack.
- Explicitly **does not perform Slack actions** (no Slack tools are configured).

## Public API
- `class SlackAgent(IntentAgent)`
  - `name`: `"Slack"`
  - `description`: `"Helps you interact with Slack for team communication and collaboration."`
  - `system_prompt`: guidance-only prompt that states tools are not available
  - `suggestions`: empty list
  - `@classmethod New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> SlackAgent`
    - Constructs and returns a configured `SlackAgent`.
    - Initializes:
      - `chat_model`: from `ModelRegistryService.get_default_chat_model()`
      - `embedding_model`: from `ModelRegistryService.get_default_embedding_model().model`
      - `tools`: `[]`
      - `intents`: two `IntentType.RAW` intents with canned guidance responses
      - `state`: provided or `AgentSharedState(thread_id="0")`
      - `configuration`: provided or `AgentConfiguration(system_prompt=SlackAgent.system_prompt)`
      - `memory`: `None`

## Configuration/Dependencies
- Depends on core agent types:
  - `naas_abi_core.services.agent.IntentAgent`: `IntentAgent`, `Intent`, `IntentType`, `AgentSharedState`, `AgentConfiguration`
- Requires Slack application module singleton:
  - `naas_abi_marketplace.applications.slack.ABIModule.get_instance()`
- Requires an initialized model registry service:
  - `abi_module.engine.services.model_registry` must be non-`None` (asserted)
  - Uses defaults:
    - `get_default_chat_model()`
    - `get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.slack.agents.SlackAgent import SlackAgent

agent = SlackAgent.New()
# Interact with `agent` via the IntentAgent interface from naas_abi_core.
```

## Caveats
- No Slack API/tools are configured (`tools = []`), so the agent must not claim to read/post/manage real Slack channels or messages.
- `New()` asserts the model registry is initialized; construction will fail if it is not.

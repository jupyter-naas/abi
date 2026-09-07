# GoogleAnalyticsAgent

## What it is
A lightweight `IntentAgent` specialized for **general guidance** on Google Analytics features, reporting, and analytics concepts. It is explicitly configured with **no tools**, so it cannot access or fetch real Google Analytics data.

## Public API
- **Class: `GoogleAnalyticsAgent(IntentAgent)`**
  - Class attributes:
    - `name`: `"Google Analytics"`
    - `description`: `"Helps you interact with Google Analytics for website analytics and data insights."`
    - `system_prompt`: System instructions emphasizing guidance-only behavior (no tool access).
    - `suggestions`: Empty list.
  - **`@classmethod New(cls, agent_shared_state=None, agent_configuration=None) -> GoogleAnalyticsAgent`**
    - Factory method that builds and returns a configured agent instance.
    - Pulls default chat and embedding models from the module engine’s model registry.
    - Registers:
      - `tools = []` (no integrations)
      - Two RAW intents for general informational responses.

## Configuration/Dependencies
- **Core types**
  - `naas_abi_core.services.agent.IntentAgent`: `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- **Module dependency**
  - `naas_abi_marketplace.applications.google_analytics.ABIModule`
    - Used to access `engine.services.model_registry`.
    - Requires the `ModelRegistryService` to be initialized; otherwise `assert` fails.
- **Defaults**
  - `agent_configuration`: defaults to `AgentConfiguration(system_prompt=GoogleAnalyticsAgent.system_prompt)`
  - `agent_shared_state`: defaults to `AgentSharedState(thread_id="0")`
- **Models**
  - `chat_model`: `registry.get_default_chat_model()`
  - `embedding_model`: `registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.google_analytics.agents.GoogleAnalyticsAgent import GoogleAnalyticsAgent

agent = GoogleAnalyticsAgent.New()
print(agent.name)
print(agent.description)
```

## Caveats
- No tools are configured (`tools = []`), so the agent **cannot** query Google Analytics APIs or retrieve actual analytics data.
- Requires the module engine’s `model_registry` to be initialized; otherwise agent creation fails with an assertion error.

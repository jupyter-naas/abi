# GoogleAnalyticsAgent

## What it is
A minimal `IntentAgent` implementation configured to provide **general guidance** about Google Analytics features, reporting, and analytics concepts. It does **not** include tools to access real Google Analytics data.

## Public API
- **Constants**
  - `NAME`: Display name (`"Google Analytics"`).
  - `DESCRIPTION`: Short description of the agent’s purpose.
  - `SYSTEM_PROMPT`: System prompt defining role, objectives, constraints (notably: no tool/data access).
  - `SUGGESTIONS`: Empty list (no suggestions provided).

- **Functions**
  - `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`  
    Creates and returns a configured `GoogleAnalyticsAgent`:
    - Uses GPT model from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`.
    - Registers **no tools** (`tools = []`).
    - Adds two RAW intents providing explanatory responses.

- **Classes**
  - `class GoogleAnalyticsAgent(IntentAgent)`  
    No additional behavior; inherits all functionality from `IntentAgent`.

## Configuration/Dependencies
- Depends on core agent framework types from:
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Chat model dependency:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (uses `model.model`)
- Default configuration:
  - If `agent_configuration` is not provided, `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` is used.
- Shared state:
  - If `agent_shared_state` is not provided, a new `AgentSharedState()` is created.

## Usage
```python
from naas_abi_marketplace.applications.google_analytics.agents.GoogleAnalyticsAgent import create_agent

agent = create_agent()
print(agent.name)          # "Google Analytics"
print(agent.description)   # Helps you interact with Google Analytics...
```

## Caveats
- **No tools are configured** (`tools = []`), so the agent cannot access Google Analytics APIs or retrieve real analytics data.
- The system prompt explicitly constrains the agent to **general information and guidance only**.

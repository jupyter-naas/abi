# InstagramAgent

## What it is
`InstagramAgent` is an `IntentAgent` specialized for Instagram-related guidance (social media management, content creation, engagement). It is configured with **no Instagram tools**, so it provides **general information only** via predefined intents and a system prompt that enforces this limitation.

## Public API
- `class InstagramAgent(IntentAgent)`
  - Agent definition with class attributes:
    - `name = "Instagram"`
    - `description = "Helps you interact with Instagram for social media management and content operations."`
    - `system_prompt` describing role/objective/constraints (no tool access)
    - `suggestions = []`
- `InstagramAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> InstagramAgent`
  - Factory constructor that:
    - Retrieves default chat and embedding models from the application `ABIModule` model registry.
    - Configures `tools` as an empty list.
    - Registers two RAW intents for:
      - Instagram feature information
      - Content management and engagement concepts
    - Defaults:
      - `AgentConfiguration(system_prompt=InstagramAgent.system_prompt)` if not provided
      - `AgentSharedState(thread_id="0")` if not provided

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Depends on application module:
  - `naas_abi_marketplace.applications.instagram.ABIModule.get_instance()`
  - Requires `abi_module.engine.services.model_registry` to be initialized (asserted)
- Models:
  - `chat_model = registry.get_default_chat_model()`
  - `embedding_model = registry.get_default_embedding_model().model`
- Tools:
  - None (`tools = []`)

## Usage
```python
from naas_abi_marketplace.applications.instagram.agents.InstagramAgent import InstagramAgent

agent = InstagramAgent.New()
print(agent.name)
print(agent.description)
```

## Caveats
- No Instagram actions are possible from this agent as configured (`tools` is empty).
- Creation requires the Instagram `ABIModule` engine/model registry to be initialized; otherwise the assertion will fail.
- The system prompt constrains the agent to **general guidance only** (no account/content access, no operational actions).

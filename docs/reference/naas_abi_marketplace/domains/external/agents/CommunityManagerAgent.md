# CommunityManagerAgent

## What it is
- A specialized `Agent` implementation configured as a community management expert (strategy, engagement, social media, events, analytics).
- Provides metadata (name/description/logo), a structured `system_prompt`, and pre-defined UI-style `suggestions`.
- Factory method `New()` builds an instance using the default chat model from the Naas ABI model registry.

## Public API
- **Class: `CommunityManagerAgent(Agent)`**
  - **Class attributes**
    - `name`: Agent display name (`"CommunityManager"`).
    - `description`: Human-readable role description.
    - `logo_url`: Path to logo asset.
    - `system_prompt`: Prompt template with a `[TOOLS]` placeholder that is replaced during construction when no configuration is provided.
    - `suggestions`: List of suggested tasks (label/value/description dicts).
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> CommunityManagerAgent`**
    - Creates a new agent instance.
    - Pulls the default chat model via `get_default_model_registry().get_default_chat_model()`.
    - If `agent_configuration` is not provided, creates one by injecting available tools into `system_prompt`.
    - If `agent_shared_state` is not provided, sets `thread_id="0"`.
    - Note: In this file, `tools` and `agents` are initialized as empty lists.
  - **`onHumanMessage(self, message: AnyMessage) -> None`**
    - Hook called when the user sends a new message. (No implementation in this file.)
  - **`onAImessage(self, message: AnyMessage, agent_name: str) -> None`**
    - Hook called when an AI message is emitted. (No implementation in this file.)

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Runtime requirement**
  - A default model registry must be initialized; otherwise `New()` raises an assertion error:
    - `"ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.domains.external.agents.CommunityManagerAgent import CommunityManagerAgent

agent = CommunityManagerAgent.New()

print(agent.name)
print(agent.description)
```

## Caveats
- `New()` depends on an initialized default model registry; without it, agent creation fails.
- `onHumanMessage` and `onAImessage` are defined but empty in this module (no side effects or logging here).
- This agent registers no tools or sub-agents in this file (`tools=[]`, `agents=[]`).

# ContentCreatorAgent

## What it is
- A LangChain-compatible `Agent` implementation for content creation tasks (copywriting, social media, video scripts, creative campaigns).
- Provides default metadata (name/description/logo), a system prompt, and UI-style suggestion templates.
- Factory method (`New`) builds an instance using the default chat model from the core model registry.

## Public API
- `class ContentCreatorAgent(Agent)`
  - Class attributes:
    - `name`: `"ContentCreator"`
    - `description`: human-readable agent description
    - `logo_url`: asset path to agent logo
    - `system_prompt`: markdown-like prompt template with a `[TOOLS]` placeholder
    - `suggestions`: list of dict templates for common user intents
  - `@classmethod New(cls, agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> ContentCreatorAgent`
    - Creates a configured agent:
      - Loads the default chat model from `get_default_model_registry()`
      - Initializes `tools` and `agents` as empty lists
      - If `agent_configuration` is not provided, injects tool descriptions into `system_prompt` (empty if no tools)
      - If `agent_shared_state` is not provided, uses `AgentSharedState(thread_id="0")`
  - `onHumanMessage(self, message: AnyMessage) -> None`
    - Hook called when a human/user message is received (no implementation in this file).
  - `onAImessage(self, message: AnyMessage, agent_name: str) -> None`
    - Hook called when an AI message is emitted (no implementation in this file).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent` (`Agent`, `AgentConfiguration`, `AgentSharedState`)
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- Requires the core model registry to be initialized:
  - `get_default_model_registry()` must return a non-`None` registry.
  - The registry must provide `get_default_chat_model()`.

## Usage
```python
from naas_abi_marketplace.domains.external.agents.ContentCreatorAgent import ContentCreatorAgent

agent = ContentCreatorAgent.New()

# The agent is now configured with:
# - default chat model from the model registry
# - empty tools list
# - default thread_id "0"
print(agent.name)
```

## Caveats
- `New()` asserts that the model registry is initialized; it will raise an `AssertionError` if not.
- `onHumanMessage` and `onAImessage` are defined but intentionally do nothing in this implementation.
- No tools are registered in this file; the `[TOOLS]` section in the prompt will be empty unless tools are added elsewhere.

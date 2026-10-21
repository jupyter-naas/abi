# ContentStrategistAgent

## What it is
- An `Agent` implementation focused on content strategy tasks (strategy, editorial planning, audience analysis, content optimization, SEO, performance).
- Provides:
  - A predefined `system_prompt` template (with a `[TOOLS]` placeholder).
  - UI-friendly `suggestions` for common tasks.
  - Optional message hooks for observing inbound and outbound messages.

## Public API
- `class ContentStrategistAgent(Agent)`
  - Class attributes:
    - `name`: `"ContentStrategist"`
    - `description`: short human-readable description
    - `logo_url`: `"naas_abi_marketplace/domains/plans/assets/public/content-strategist.png"`
    - `system_prompt`: prompt with operating guidelines, constraints, and `[TOOLS]` placeholder
    - `suggestions`: list of suggestion dicts (`label`, `value`, `description`)
  - `@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> ContentStrategistAgent`
    - Factory constructor that:
      - Fetches the default chat model from the default model registry.
      - Builds a default `AgentConfiguration` by injecting available tools into `system_prompt` if none is provided.
      - Creates a default `AgentSharedState(thread_id="0")` if none is provided.
      - Instantiates the agent with `tools=[]`, `agents=[]`, and `memory=None`.
  - Message hooks (no-op by default; intended for instrumentation/observation):
    - `onHumanMessage(self, message: AnyMessage) -> None`
      - Called once per user turn before the model is invoked.
    - `onAImessage(self, message: AnyMessage, agent_name: str) -> None`
      - Called on AI messages emitted by this agent or sub-agents (tool-call-only messages are not reported).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry()`
  - `langchain_core.messages.AnyMessage`
- Runtime expectations:
  - `New()` asserts that the default model registry is initialized:
    - `assert registry is not None, "ModelRegistryService not initialized"`
- Tools/sub-agents:
  - `tools` and `agents` are initialized as empty lists in `New()`.

## Usage
```python
from naas_abi_marketplace.domains.plans.agents.ContentStrategistAgent import ContentStrategistAgent

agent = ContentStrategistAgent.New()
# Message exchange is managed by the naas_abi_core runtime hosting the Agent.
```

## Caveats
- `New()` fails if the default model registry service is not initialized.
- Tool injection into `system_prompt` currently injects an empty tools section because `tools = []` in `New()`.
- `onHumanMessage` and `onAImessage` do nothing unless you implement logic in their bodies.

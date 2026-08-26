# ContentAnalystAgent

## What it is
- `ContentAnalystAgent` is an `Agent` specialization for content performance analysis, audience insights, SEO optimization, and content strategy recommendations.
- It defines a fixed `system_prompt` template (with a `[TOOLS]` placeholder) and UI suggestion templates.
- The `New()` factory wires the agent to the workspace’s default chat model.

## Public API
- **Class: `ContentAnalystAgent(Agent)`**
  - **Class attributes**
    - `name`: `"ContentAnalyst"`
    - `description`: Human-readable description of the agent’s specialization.
    - `logo_url`: `"naas_abi_marketplace/domains/operations/assets/public/content-analyst.png"`
    - `system_prompt`: Prompt template containing a `[TOOLS]` placeholder.
    - `suggestions`: List of dicts used as prompt/suggestion templates (Strategy, Analysis, Optimization, Planning).
  - **Class methods**
    - `New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> ContentAnalystAgent`
      - Fetches the default chat model via the default model registry.
      - Builds an `AgentConfiguration` from `system_prompt` if none is provided (replaces `[TOOLS]` with a generated tools section).
      - Creates a default `AgentSharedState(thread_id="0")` if none is provided.
      - Instantiates the agent with `tools=[]`, `agents=[]`, `memory=None`.
  - **Instance methods (message hooks)**
    - `onHumanMessage(message: AnyMessage) -> None`
      - Hook called when a user message is received (no-op by default).
    - `onAImessage(message: AnyMessage, agent_name: str) -> None`
      - Hook called when an AI message is emitted by this agent or sub-agents (no-op by default).

## Configuration/Dependencies
- **Depends on `naas_abi_core`**
  - `naas_abi_core.engine.context.get_default_model_registry()` to obtain the model registry.
  - `naas_abi_core.services.agent.Agent` types:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
- **Depends on `langchain_core.messages.AnyMessage`** for hook method typing.
- **Runtime requirement**
  - `New()` asserts the default model registry is initialized: `"ModelRegistryService not initialized"`.

## Usage
```python
from naas_abi_marketplace.domains.operations.agents.ContentAnalystAgent import ContentAnalystAgent

agent = ContentAnalystAgent.New()
```

## Caveats
- `New()` will raise an `AssertionError` if the default model registry is not initialized.
- `tools` and `agents` are instantiated as empty lists in `New()`, so `[TOOLS]` becomes an empty section unless you provide your own `AgentConfiguration`.
- Message hooks are no-ops unless implemented; per docstring comments, return values are ignored and exceptions are swallowed by the runtime.

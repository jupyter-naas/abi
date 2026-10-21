# AccountExecutiveAgent

## What it is
- An `Agent` implementation configured as an “Account Executive” persona for client relationship management, sales strategy, account growth, and revenue optimization.
- Provides a factory constructor (`New`) that retrieves the default chat model from the Naas ABI model registry and builds an `AgentConfiguration` from the class `system_prompt` (injecting a tools section).

## Public API
- **Class: `AccountExecutiveAgent(Agent)`**
  - **Class attributes**
    - `name`: `"AccountExecutive"`.
    - `description`: Expertise summary for the agent.
    - `logo_url`: `"naas_abi_marketplace/domains/operations/assets/public/account-executive.png"`.
    - `system_prompt`: Prompt template containing a `[TOOLS]` placeholder.
    - `suggestions`: List of suggestion dicts (labels/values/descriptions) for strategy, analysis, optimization, planning.
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> AccountExecutiveAgent`**
    - Creates and returns an initialized agent.
    - Behavior:
      - Pulls the workspace default chat model via `naas_abi_core.engine.context.get_default_model_registry().get_default_chat_model()`.
      - Uses `tools = []` and `agents = []`.
      - If `agent_configuration` is not provided, builds one by replacing `[TOOLS]` in `system_prompt` with a bullet list derived from `tools` (empty string when no tools).
      - If `agent_shared_state` is not provided, creates `AgentSharedState(thread_id="0")`.
      - Instantiates the base `Agent` with `memory=None`, plus the computed `state` and `configuration`.
  - **Message hooks (no-op by default)**
    - `onHumanMessage(message: AnyMessage) -> None`: Called once per turn before the message reaches the model.
    - `onAImessage(message: AnyMessage, agent_name: str) -> None`: Called when an AI message is emitted by this agent or any sub-agent (tool-call-only messages are not reported).

## Configuration/Dependencies
- **Naas ABI Core**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
    - Must be initialized; otherwise `New()` raises an `AssertionError`.
- **LangChain Core**
  - `langchain_core.messages.AnyMessage` (used in hook type hints)

## Usage
```python
from naas_abi_marketplace.domains.operations.agents.AccountExecutiveAgent import (
    AccountExecutiveAgent
)

agent = AccountExecutiveAgent.New()

# Optional instrumentation hooks (no behavior unless you implement it)
# agent.onHumanMessage(message)
# agent.onAImessage(message, agent_name="AccountExecutive")
```

## Caveats
- `AccountExecutiveAgent.New()` asserts if the model registry is not initialized: `"ModelRegistryService not initialized"`.
- The agent is created with **no tools** and **no sub-agents** (`tools = []`, `agents = []`).
- `onHumanMessage` / `onAImessage` are defined as observation hooks but contain no logic by default.

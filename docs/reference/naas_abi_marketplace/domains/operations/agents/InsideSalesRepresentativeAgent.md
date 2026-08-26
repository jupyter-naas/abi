# InsideSalesRepresentativeAgent

## What it is
- An `Agent` implementation configured as an inside sales expert (remote sales, phone prospecting, CRM management, inbound lead conversion).
- Provides a predefined `system_prompt` (with a `[TOOLS]` placeholder) and a set of suggestion templates.
- Includes optional message hooks (`onHumanMessage`, `onAImessage`) intended for lightweight observability.

## Public API
- **Class `InsideSalesRepresentativeAgent(Agent)`**
  - **Class attributes**
    - `name`: `"InsideSalesRepresentative"`
    - `description`: Inside sales specialization summary.
    - `logo_url`: Asset path for the agent logo.
    - `system_prompt`: Base system prompt containing `[TOOLS]` placeholder.
    - `suggestions`: List of suggestion template dicts (Strategy/Analysis/Optimization/Planning).
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> InsideSalesRepresentativeAgent`**
    - Factory constructor.
    - Retrieves the workspace default chat model from `get_default_model_registry().get_default_chat_model()`.
    - Builds a default `AgentConfiguration` by replacing `[TOOLS]` with formatted tool descriptions (empty by default).
    - Uses `AgentSharedState(thread_id="0")` when no shared state is provided.
  - **Message hooks**
    - `onHumanMessage(message: AnyMessage) -> None`: Called before a human message reaches the model (no-op by default).
    - `onAImessage(message: AnyMessage, agent_name: str) -> None`: Called when an AI message is emitted by this agent or sub-agents (no-op by default).

## Configuration/Dependencies
- **Depends on**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Runtime requirement**
  - `get_default_model_registry()` must return a registry; `New()` asserts this (`"ModelRegistryService not initialized"`).

## Usage
```python
from naas_abi_marketplace.domains.operations.agents.InsideSalesRepresentativeAgent import (
    InsideSalesRepresentativeAgent,
)

agent = InsideSalesRepresentativeAgent.New()
```

## Caveats
- `New()` will fail if the default model registry is not initialized (assertion).
- `tools` and `agents` are constructed as empty lists in `New()`, so the `[TOOLS]` section is blank in the default `system_prompt`.
- Message hooks run inline on the streaming thread (per comments); keep them fast if implemented.

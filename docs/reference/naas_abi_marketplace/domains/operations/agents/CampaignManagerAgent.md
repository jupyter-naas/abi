# CampaignManagerAgent

## What it is
- An `Agent` implementation configured as a “Campaign Manager” expert.
- Ships with predefined metadata (`name`, `description`, `logo_url`), a `system_prompt`, UI `suggestions`, and a `New()` factory that attaches the workspace default chat model.

## Public API
- **Class: `CampaignManagerAgent(Agent)`**
  - **Class attributes**
    - `name`: `"CampaignManager"`
    - `description`: Campaign manager specialization summary.
    - `logo_url`: `"naas_abi_marketplace/domains/operations/assets/public/campaign-manager.png"`
    - `system_prompt`: Prompt template containing role/objective/guidelines/constraints and a `[TOOLS]` placeholder.
    - `suggestions`: List of dicts used for prefilled prompts (Strategy, Analysis, Optimization, Planning).
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> CampaignManagerAgent`**
    - Builds and returns an instance.
    - Fetches the default chat model via the default model registry.
    - If `agent_configuration` is omitted, creates one by replacing `[TOOLS]` in `system_prompt` with a generated tools section (empty in this file).
    - If `agent_shared_state` is omitted, creates `AgentSharedState(thread_id="0")`.
  - **Message hooks (no-op by default)**
    - `onHumanMessage(message: AnyMessage) -> None`: Called once per user turn before the message reaches the model.
    - `onAImessage(message: AnyMessage, agent_name: str) -> None`: Called on emitted AI messages (excluding tool-call-only messages), for this agent and any sub-agents.

## Configuration/Dependencies
- **Imports/Dependencies**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry()` to obtain the default chat model
  - `langchain_core.messages.AnyMessage` for hook method signatures
- **Runtime requirements**
  - The default model registry must be initialized (used by `New()`).

## Usage
```python
from naas_abi_marketplace.domains.operations.agents.CampaignManagerAgent import (
    CampaignManagerAgent,
)

agent = CampaignManagerAgent.New()
```

## Caveats
- `CampaignManagerAgent.New()` raises an `AssertionError` if the default model registry is not initialized (`"ModelRegistryService not initialized"`).
- `tools` and `agents` are empty lists in this implementation, so the `[TOOLS]` section in the prompt is blank unless extended elsewhere.
- `onHumanMessage` and `onAImessage` are observation hooks; their bodies are empty unless you add logic.

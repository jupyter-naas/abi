# DataEngineerAgent

## What it is
- A specialized `Agent` for data engineering tasks (pipelines, ETL/ELT, data architecture, performance optimization).
- Provides predefined identity metadata, a system prompt template (with a `[TOOLS]` placeholder), and a set of user prompt suggestions.
- Instantiated via `New()`, which pulls the default chat model from the global model registry.

## Public API
- **Class: `DataEngineerAgent(Agent)`**
  - **Class attributes**
    - `name`: `"DataEngineer"`
    - `description`: Describes the agent’s data engineering expertise.
    - `logo_url`: `"naas_abi_marketplace/domains/signals/assets/public/data-engineer.png"`
    - `system_prompt`: System prompt template containing a `[TOOLS]` placeholder.
    - `suggestions`: List of prompt templates:
      - Pipeline Design
      - Performance Issue
      - Architecture Review
      - Data Quality
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> DataEngineerAgent`**
    - Creates an instance using:
      - `get_default_model_registry().get_default_chat_model()`
      - `tools = []`, `agents = []`
      - Default `AgentSharedState(thread_id="0")` if not provided
      - Default `AgentConfiguration` if not provided, where `[TOOLS]` is replaced by a rendered tool list (empty in this implementation)
  - **`onHumanMessage(message: AnyMessage) -> None`**
    - Hook called when a user message is received (no implementation here).
  - **`onAImessage(message: AnyMessage, agent_name: str) -> None`**
    - Hook called when an AI message is emitted (no implementation here).

## Configuration/Dependencies
- **Depends on**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Model registry requirement**
  - `New()` asserts the default model registry exists: `"ModelRegistryService not initialized"`.

## Usage
```python
from naas_abi_marketplace.domains.signals.agents.DataEngineerAgent import DataEngineerAgent

agent = DataEngineerAgent.New()

print(agent.name)
print(agent.description)
```

## Caveats
- `New()` will fail with an assertion error if the default model registry is not initialized.
- No tools are configured by default (`tools = []`), so the `[TOOLS]` section in the system prompt will be empty unless an `agent_configuration` is provided externally.
- `onHumanMessage` and `onAImessage` are declared but contain no behavior in this file.

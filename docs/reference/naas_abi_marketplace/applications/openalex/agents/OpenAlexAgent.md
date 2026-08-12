# OpenAlexAgent

## What it is
- An `IntentAgent` specialization that defines an “OpenAlex” agent persona.
- Provides general guidance about OpenAlex (no tools are configured; it does not retrieve real OpenAlex data).

## Public API
- `class OpenAlexAgent(IntentAgent)`
  - Agent configuration via class attributes:
    - `name = "OpenAlex"`
    - `description = "Helps you interact with OpenAlex for academic research and publication data."`
    - `system_prompt` (persona, objectives, constraints)
    - `suggestions = []`
- `OpenAlexAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> OpenAlexAgent`
  - Factory constructor that:
    - Pulls the default chat and embedding models from the app’s model registry.
    - Configures:
      - `tools = []`
      - Two RAW intents for informational responses.
    - Creates defaults when not provided:
      - `AgentConfiguration(system_prompt=OpenAlexAgent.system_prompt)`
      - `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Runtime dependency used inside `New()`:
  - `naas_abi_marketplace.applications.openalex.ABIModule.get_instance()`
  - Requires `abi_module.engine.services.model_registry` to be initialized.
- Model selection:
  - `chat_model = registry.get_default_chat_model()`
  - `embedding_model = registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.openalex.agents.OpenAlexAgent import OpenAlexAgent

agent = OpenAlexAgent.New()

# Use via IntentAgent's interface (method names depend on IntentAgent implementation).
# Example (placeholder): agent.run("What is OpenAlex?")
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot search or fetch OpenAlex data.
- `New()` asserts the model registry exists; it will fail if the application engine/model registry is not initialized.

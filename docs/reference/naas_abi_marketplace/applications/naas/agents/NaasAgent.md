# NaasAgent

## What it is
A Naas-specific `Agent` subclass that preconfigures:
- A Naas-focused system prompt
- Naas integration tools (authenticated via a Naas API key)
- The default chat model from the app’s model registry

## Public API
- `class NaasAgent(Agent)`
  - Metadata (class attributes):
    - `name = "Naas"`
    - `description = "Manage all resources on Naas: workspaces, agents, ontologies, users, secrets, storage."`
    - `avatar_url = "https://raw.githubusercontent.com/.../Naas.png"`
    - `system_prompt = """..."""` (Naas operating instructions and constraints)
    - `suggestions: list[str] = []`
  - Constructors:
    - `@classmethod New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> NaasAgent`
      - Builds and returns a configured `NaasAgent`.
      - Uses the default chat model from `ABIModule.get_instance().engine.services.model_registry`.
      - Attaches tools from `naas_abi_marketplace.applications.naas.integrations.NaasIntegration.as_tools(...)`.
      - Defaults:
        - `AgentConfiguration(system_prompt=cls.system_prompt)` if not provided
        - `AgentSharedState(thread_id="0")` if not provided

## Configuration/Dependencies
- **ABIModule**
  - Used to access:
    - `engine.services.model_registry` (must be initialized)
    - `configuration.naas_api_key`
- **Model**
  - Obtained via: `registry.get_default_chat_model()`
- **Tools**
  - Created via:
    - `NaasIntegrationConfiguration(api_key=naas_api_key)`
    - `as_tools(naas_integration_config)`

## Usage
```python
from naas_abi_marketplace.applications.naas.agents.NaasAgent import NaasAgent

agent = NaasAgent.New()
# Use `agent` via the base `Agent` interface from naas_abi_core.
```

## Caveats
- `ModelRegistryService` must be initialized; otherwise `NaasAgent.New()` will raise an assertion error.
- If `ABIModule.get_instance().configuration.naas_api_key` is missing/invalid, the integration tools may not function as expected.

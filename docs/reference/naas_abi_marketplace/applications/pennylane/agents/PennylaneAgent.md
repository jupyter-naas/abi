# PennylaneAgent

## What it is
- A specialized `Agent` that wires Pennylane integration tools into the core `naas_abi_core` agent framework.
- Provides fixed metadata (name/description/avatar) and a French system prompt oriented around accounting workflows and tool usage.

## Public API
- `class PennylaneAgent(Agent)`
  - Class attributes:
    - `name`: `"Pennylane"`
    - `description`: `"A Pennylane Agent for managing accounting and financial operations."`
    - `avatar_url`: `"https://www.pennylane.tech/favicon.ico"`
    - `system_prompt`: French instructions, including asking users to set `PENNYLANE_API_TOKEN` if tools are unavailable.
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> PennylaneAgent`
    - Creates and returns a configured `PennylaneAgent` with:
      - Default chat model from the application’s `ModelRegistryService`
      - Pennylane integration tools via `as_tools(PennylaneIntegrationConfiguration(api_key=...))`
      - Defaults:
        - `AgentConfiguration(system_prompt=cls.system_prompt)` if not provided
        - `AgentSharedState(thread_id="0")` if not provided
      - `MemorySaver()` memory implementation

## Configuration/Dependencies
- Depends on Pennylane application module:
  - `naas_abi_marketplace.applications.pennylane.ABIModule.get_instance()`
  - Reads `module.configuration.pennylane_api_token` to build:
    - `PennylaneIntegrationConfiguration(api_key=pennylane_api_token)`
- Requires model registry to be initialized:
  - `abi_module.engine.services.model_registry` must be non-`None` (asserted)
  - Uses `registry.get_default_chat_model()`
- Key imports:
  - Core agent: `Agent`, `AgentConfiguration`, `AgentSharedState`, `MemorySaver`
  - Integration tooling: `PennylaneIntegrationConfiguration`, `as_tools`

## Usage
```python
from naas_abi_marketplace.applications.pennylane.agents.PennylaneAgent import PennylaneAgent

agent = PennylaneAgent.New()

# Use the base Agent interface (methods are defined on naas_abi_core.services.agent.Agent.Agent)
# Example (method name depends on your Agent implementation):
# result = agent.invoke("Récupère la liste des factures.")
# print(result)
```

## Caveats
- `ModelRegistryService` must be initialized; otherwise `New()` raises an assertion error.
- If `pennylane_api_token` is missing/invalid, the generated tools may not function; the system prompt instructs users to configure `PENNYLANE_API_TOKEN` in `.env`.
- This file does not define interaction methods (e.g., `invoke`, `run`); they are inherited from `Agent`.

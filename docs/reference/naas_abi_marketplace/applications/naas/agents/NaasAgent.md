# NaasAgent

## What it is
A thin wrapper around the core `Agent` that wires a Naas-specific system prompt and Naas integration tools (via an API key) to manage Naas resources (workspaces, agents, ontologies, users, secrets, storage).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Agent`
  - Builds and returns a configured `NaasAgent` instance.
  - Loads Naas API key from `ABIModule.get_instance().configuration.naas_api_key`.
  - Uses the `gpt_4_1_mini` chat model.
  - Attaches tools created from `NaasIntegrationConfiguration` via `as_tools(...)`.
  - Defaults:
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided.
    - `AgentSharedState(thread_id="0")` if not provided.

- `class NaasAgent(Agent)`
  - No additional behavior; inherits everything from `naas_abi_core.services.agent.Agent.Agent`.

## Configuration/Dependencies
- **Naas API key**
  - Read from: `ABIModule.get_instance().configuration.naas_api_key`
  - Passed into: `NaasIntegrationConfiguration(api_key=...)`
- **Model**
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
- **Tools**
  - `naas_abi_marketplace.applications.naas.integrations.NaasIntegration.as_tools`
- **Core types**
  - `Agent`, `AgentConfiguration`, `AgentSharedState` from `naas_abi_core.services.agent.Agent`

## Usage
```python
from naas_abi_marketplace.applications.naas.agents.NaasAgent import create_agent

agent = create_agent()
# agent can now be used with the underlying Agent interface (methods defined in naas_abi_core)
```

## Caveats
- If the Naas API key is missing/invalid in `ABIModule` configuration, the integration tools may not function (tool availability depends on correct authentication).
- `NaasAgent` itself adds no behavior; all runtime capabilities come from the base `Agent`, selected model, and attached tools.

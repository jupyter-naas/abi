# SalesforceAgent

## What it is
- An `IntentAgent` specialization for providing **general guidance** on Salesforce CRM, sales pipeline management, and best practices.
- **No tools are configured**, so it cannot access or mutate real Salesforce data.

## Public API
- `class SalesforceAgent(IntentAgent)`
  - Agent defaults:
    - `name = "Salesforce"`
    - `description = "Helps you interact with Salesforce for CRM and sales operations."`
    - `system_prompt`: guidance-oriented prompt explicitly stating no tool access
    - `suggestions = []`
- `SalesforceAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> SalesforceAgent`
  - Creates and returns a configured `SalesforceAgent`.
  - Initializes:
    - `tools`: `[]`
    - `intents`: two `IntentType.RAW` intents (Salesforce features; CRM/pipeline concepts)
    - `agent_configuration`: defaults to `AgentConfiguration(system_prompt=cls.system_prompt)` if not provided
    - `agent_shared_state`: defaults to `AgentSharedState(thread_id="0")` if not provided
    - `chat_model` / `embedding_model`: pulled from the application `ModelRegistryService` defaults

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on Salesforce application module wiring:
  - `from naas_abi_marketplace.applications.salesforce import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`
    - Requires the model registry service to be initialized (`assert registry is not None`)
    - Uses:
      - `registry.get_default_chat_model()`
      - `registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.salesforce.agents.SalesforceAgent import SalesforceAgent
from naas_abi_core.services.agent.IntentAgent import AgentSharedState

agent = SalesforceAgent.New(agent_shared_state=AgentSharedState(thread_id="1"))

# Interact with `agent` using the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No Salesforce tools are registered (`tools = []`), so the agent:
  - cannot connect to Salesforce,
  - cannot read/write CRM objects (leads, accounts, opportunities),
  - only provides general, non-data-backed guidance.
- Creation requires a properly initialized `ABIModule` and `model_registry`; otherwise, instantiation will fail on the registry assertion.

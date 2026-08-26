# SendGridAgent

## What it is
- An `IntentAgent` implementation for the SendGrid application.
- Provides a default system prompt and two informational (`RAW`) intents.
- Factory method `New()` wires models from the module engine, reads the SendGrid API key from module configuration, and attaches tools from the SendGrid integration.

## Public API
- `class SendGridAgent(IntentAgent)`
  - Agent metadata:
    - `name = "SendGrid"`
    - `description = "Helps you interact with SendGrid for email delivery and management."`
    - `system_prompt` (string prompt describing constraints and guidance)
    - `suggestions = []`
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> SendGridAgent`
    - Creates and returns a configured `SendGridAgent` instance.
    - Resolves:
      - `chat_model` from `ABIModule.get_instance().engine.services.model_registry.get_default_chat_model()`
      - `embedding_model` from `...get_default_embedding_model().model`
      - `api_key` from `ABIModule.get_instance().configuration.sendgrid_api_key`
      - `tools` via `SendGridIntegrationConfiguration(api_key=api_key)` + `as_tools(...)`
    - Sets defaults when not provided:
      - `agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)`
      - `agent_shared_state = AgentSharedState(thread_id="0")`
    - Adds two default `Intent` entries (type `IntentType.RAW`) with informational responses.

## Configuration/Dependencies
- Agent framework types:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType` from `naas_abi_core.services.agent.IntentAgent`
- Module / runtime:
  - `naas_abi_marketplace.applications.sendgrid.ABIModule`
  - Requires the module engine `services.model_registry` to be initialized (`assert registry is not None`)
- SendGrid integration:
  - `SendGridIntegrationConfiguration`, `as_tools` from `naas_abi_marketplace.applications.sendgrid.integrations.SendGridIntegration`
- Configuration value:
  - `ABIModule.get_instance().configuration.sendgrid_api_key`

## Usage
```python
from naas_abi_marketplace.applications.sendgrid.agents.SendGridAgent import SendGridAgent

agent = SendGridAgent.New()
print(agent.name)
```

## Caveats
- `New()` asserts that the model registry service is initialized; it will raise an `AssertionError` otherwise.
- The `system_prompt` states the agent does not have access to SendGrid tools, but `New()` does attach tools from `as_tools(...)`. Actual capabilities depend on the integration tools and runtime.

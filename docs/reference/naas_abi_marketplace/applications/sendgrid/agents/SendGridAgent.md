# SendGridAgent

## What it is
- An `IntentAgent` factory and thin agent class for the SendGrid application.
- Wires configuration (SendGrid API key), chat model, tools from the SendGrid integration, and a couple of default informational intents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `SendGridAgent` with:
    - `name`, `description`
    - `system_prompt`
    - integration tools created via `SendGridIntegration.as_tools(...)`
    - two default `Intent` entries (RAW informational responses)
- `class SendGridAgent(IntentAgent)`
  - No additional behavior; inherits everything from `IntentAgent`.

## Configuration/Dependencies
- Configuration source:
  - `ABIModule.get_instance().configuration.sendgrid_api_key` (used to configure the integration).
- Chat model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model` (used as `chat_model=model.model`).
- Tools/integration:
  - `naas_abi_marketplace.applications.sendgrid.integrations.SendGridIntegration`:
    - `SendGridIntegrationConfiguration(api_key=...)`
    - `as_tools(integration_config)` to produce the `tools` list.
- Agent framework types:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType` from `naas_abi_core.services.agent.IntentAgent`.

## Usage
```python
from naas_abi_marketplace.applications.sendgrid.agents.SendGridAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent configured for SendGrid.
# How you run/chat with it depends on the IntentAgent runtime in naas_abi_core.
print(agent.name)
```

## Caveats
- The module-level `SYSTEM_PROMPT` states the agent “currently do[es] not have access to SendGrid tools”, but `create_agent()` does attach tools from `SendGridIntegration.as_tools(...)`. Actual capabilities depend on what those tools implement and whether the API key is correctly configured.

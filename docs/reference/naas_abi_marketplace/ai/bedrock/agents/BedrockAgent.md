# BedrockAgent

## What it is
An `IntentAgent` configured as an **AWS Bedrock**-branded agent. It wires a default chat model (`CLAUDE_SONNET_5`), a system prompt, and a set of intents that route Bedrock-related user requests to an `call_model` intent target.

## Public API
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
  - Factory that builds and returns a `BedrockAgent` instance.
  - Sets up:
    - `chat_model` from the marketplace Bedrock module/model registry (`CanonicalModelId.CLAUDE_SONNET_5`)
    - `system_prompt` (with tool list injected; tools list is empty in this file)
    - `intents` mapping common Bedrock model phrases to the `call_model` target
    - default `AgentSharedState(thread_id="0")` if none provided
    - default `AgentConfiguration(system_prompt=...)` if none provided

- `class BedrockAgent(IntentAgent)`
  - Minimal subclass that sets class attributes:
    - `name = "AWS Bedrock"`
    - `description = "... unified, IAM-authenticated API."`

## Configuration/Dependencies
- Depends on core agent types from `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses:
  - `naas_abi_core.models.Model.CanonicalModelId` (selects `CLAUDE_SONNET_5`)
  - `naas_abi_marketplace.ai.bedrock.ABIModule` (to access `engine.services.model_registry.get_chat_model(...)`)
- The system prompt includes guidance to verify AWS credentials and region/model availability, but credential handling is not implemented in this file.

## Usage
```python
from naas_abi_marketplace.ai.bedrock.agents.BedrockAgent import create_agent

agent = create_agent()
print(agent.name)
```

## Caveats
- `tools` and `agents` are empty lists in this implementation; the system prompt tool section will be empty.
- The intents defined here target `"call_model"`, but this file does not implement that handler; it relies on the broader `IntentAgent` framework.

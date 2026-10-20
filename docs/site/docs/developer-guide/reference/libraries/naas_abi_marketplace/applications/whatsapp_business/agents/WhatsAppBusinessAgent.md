# WhatsAppBusinessAgent

## What it is
- A minimal `IntentAgent` wrapper for WhatsApp Business guidance.
- Ships with a system prompt and two basic informational intents.
- No tools are configured; it only provides general information (per prompt/constraints).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that returns a configured `WhatsAppBusinessAgent`.
  - Sets:
    - `name`: `"WhatsApp_Business"`
    - `description`: messaging/customer communication guidance
    - `chat_model`: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model.model`
    - `tools`: `[]` (none)
    - `intents`: two `IntentType.RAW` intents with informational responses
    - `configuration`: defaults to `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided
    - `state`: defaults to new `AgentSharedState()` if not provided
    - `memory`: `None`

- `class WhatsAppBusinessAgent(IntentAgent)`
  - Empty subclass of `IntentAgent` (no additional methods/overrides).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model` (expects `model.model` to be a chat model instance)
- Key module constants:
  - `SYSTEM_PROMPT`: instructs the agent to provide guidance only and acknowledge lack of tool access
  - `SUGGESTIONS`: empty list (unused in this file)

## Usage
```python
from naas_abi_marketplace.applications.whatsapp_business.agents.WhatsAppBusinessAgent import create_agent

agent = create_agent()
print(agent.name)  # WhatsApp_Business
```

## Caveats
- No WhatsApp Business tools are configured (`tools = []`), so the agent cannot send messages or perform real operations—only provide general guidance.

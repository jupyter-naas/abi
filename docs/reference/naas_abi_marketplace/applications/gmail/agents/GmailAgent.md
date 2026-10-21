# GmailAgent

## What it is
A Gmail-focused `IntentAgent` that provides general guidance on Gmail features and email management. It is configured **without any Gmail tools**, so it cannot access or act on real emails.

## Public API
- **Class: `GmailAgent(IntentAgent)`**
  - Class attributes:
    - `name: str = "Gmail"`
    - `description: str = "Helps you interact with Gmail for email management and operations."`
    - `system_prompt: str` — role/objectives/constraints (explicitly states no tool access)
    - `suggestions: list = []`
  - **`@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GmailAgent`**
    - Creates and returns a configured `GmailAgent`
    - Obtains default chat and embedding models from the application module model registry
    - Registers:
      - `tools = []`
      - Two `IntentType.RAW` intents with static guidance responses
    - Defaults:
      - `AgentConfiguration(system_prompt=cls.system_prompt)` if none provided
      - `AgentSharedState(thread_id="0")` if none provided

## Configuration/Dependencies
- **Core types**
  - `naas_abi_core.services.agent.IntentAgent`: `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- **Application module / model registry**
  - `from naas_abi_marketplace.applications.gmail import ABIModule`
  - Uses:
    - `ABIModule.get_instance().engine.services.model_registry.get_default_chat_model()`
    - `...get_default_embedding_model().model`
  - Fails fast if registry is missing: `assert registry is not None`

## Usage
```python
from naas_abi_marketplace.applications.gmail.agents.GmailAgent import GmailAgent

agent = GmailAgent.New()
print(agent.name)         # Gmail
print(agent.description)  # Helps you interact with Gmail for email management and operations.
```

## Caveats
- No Gmail tool integration is configured (`tools = []`):
  - Cannot read/search/send/delete/label emails
  - Only returns general guidance via the system prompt and the two RAW intents
- Requires the Gmail `ABIModule` engine/model registry to be initialized; otherwise instantiation asserts.

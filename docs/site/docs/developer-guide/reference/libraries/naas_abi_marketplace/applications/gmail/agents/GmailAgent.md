# GmailAgent

## What it is
A minimal `IntentAgent` wrapper configured to provide general guidance about Gmail (features, email management, organization). It **does not include any Gmail tools** and therefore cannot access or act on real emails.

## Public API
- **Constants**
  - `NAME`: `"Gmail"`
  - `DESCRIPTION`: Human-readable description of the agent.
  - `SYSTEM_PROMPT`: System prompt describing role/objectives/constraints (notably: no tool access).
  - `SUGGESTIONS`: Empty list (`[]`).

- **Functions**
  - `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`  
    Creates and returns a configured `GmailAgent` instance:
    - Uses `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model`
    - Registers **no tools** (`tools = []`)
    - Registers two RAW intents with static responses about Gmail features and email management
    - Uses provided `AgentSharedState` / `AgentConfiguration` or creates defaults

- **Classes**
  - `class GmailAgent(IntentAgent)`  
    Empty subclass of `IntentAgent` (inherits all behavior from `IntentAgent`).

## Configuration/Dependencies
- Depends on core agent framework types from:
  - `naas_abi_core.services.agent.IntentAgent`:
    - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Depends on a chat model defined at:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (imported inside `create_agent`)
- Default configuration:
  - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
- Tools:
  - None configured (`tools: list = []`)

## Usage
```python
from naas_abi_marketplace.applications.gmail.agents.GmailAgent import create_agent

agent = create_agent()
# agent is an IntentAgent (specifically a GmailAgent) configured for guidance-only.
print(agent.name)         # "Gmail"
print(agent.description)  # "Helps you interact with Gmail for email management and operations."
```

## Caveats
- No Gmail integration is provided:
  - The agent cannot read, search, send, delete, or label emails.
  - Responses are limited to general information and guidance based on the configured RAW intents and system prompt.

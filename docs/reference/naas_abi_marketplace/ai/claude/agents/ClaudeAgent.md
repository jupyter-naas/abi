# ClaudeAgent

## What it is
A thin wrapper around `IntentAgent` that registers a “Claude” agent with a predefined system prompt and a set of intents routed to a model callable.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `ClaudeAgent`.
  - Wires:
    - `chat_model` from `naas_abi_marketplace.ai.claude.models.claude_sonnet_3_7`
    - a system prompt (`SYSTEM_PROMPT`) with tool listing injected (tools list is empty in this module)
    - a default `AgentSharedState(thread_id="0")` if not provided
    - a default `AgentConfiguration(system_prompt=...)` if not provided
    - a set of intents that target `call_model` for analysis/writing/code tasks

- `class ClaudeAgent(IntentAgent)`
  - No additional behavior; inherits everything from `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Imports the chat model as:
  - `from naas_abi_marketplace.ai.claude.models.claude_sonnet_3_7 import model`
- System prompt text indicates usage of an Anthropic API key via environment, but this module does not read env vars directly.

## Usage
```python
from naas_abi_marketplace.ai.claude.agents.ClaudeAgent import create_agent
from naas_abi_core.services.agent.IntentAgent import AgentSharedState

agent = create_agent(agent_shared_state=AgentSharedState(thread_id="123"))
# Use `agent` via the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- This module defines no tools (`tools = []`), so the system prompt’s tool list will be empty.
- `ClaudeAgent` itself adds no methods; behavior is entirely determined by the upstream `IntentAgent` implementation and the imported `model`.

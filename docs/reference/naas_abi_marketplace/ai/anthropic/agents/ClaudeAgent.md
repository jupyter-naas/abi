# ClaudeAgent

## What it is
- A minimal `IntentAgent` wrapper for Anthropic Claude, preconfigured with metadata, a system prompt, and a set of example intents.
- Created via `create_agent()`, which wires the agent to the Claude chat model from the Naas ABI model registry.

## Public API
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
  - Builds and returns a `ClaudeAgent` instance.
  - Loads the chat model `CanonicalModelId.CLAUDE_SONNET_5` via `naas_abi_marketplace.ai.anthropic.ABIModule`.
  - Populates:
    - `name`, `description`, `chat_model`
    - `tools` (empty list)
    - `agents` (empty list)
    - `intents` (predefined list targeting `"call_model"`)
    - `state` (defaults to `AgentSharedState(thread_id="0")`)
    - `configuration` (defaults to `AgentConfiguration(system_prompt=...)`)

- `class ClaudeAgent(IntentAgent)`
  - No additional behavior; inherits all functionality from `IntentAgent`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.models.Model.CanonicalModelId`
  - `naas_abi_core.services.agent.IntentAgent` (`IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`)
  - `naas_abi_marketplace.ai.anthropic.ABIModule` (used to fetch the chat model)
- System prompt:
  - Derived from `SYSTEM_PROMPT` with a `[TOOLS]` placeholder replaced by a bullet list of tools.
  - In this implementation, `tools` is empty, so the tools section will be empty.
- Environment/API key:
  - The system prompt instructs users to set `ANTHROPIC_API_KEY` if the API is not accessible (actual enforcement is not implemented in this file).

## Usage
```python
from naas_abi_marketplace.ai.anthropic.agents.ClaudeAgent import create_agent
from naas_abi_core.services.agent.IntentAgent import AgentSharedState

agent = create_agent(agent_shared_state=AgentSharedState(thread_id="demo"))
# Use agent methods provided by IntentAgent (not defined in this file).
```

## Caveats
- `ClaudeAgent` adds no custom methods; all behavior comes from `IntentAgent`.
- `tools` and `agents` are empty by default in `create_agent()`.
- The `ANTHROPIC_API_KEY` requirement is only mentioned in the prompt; this file does not validate or load it.

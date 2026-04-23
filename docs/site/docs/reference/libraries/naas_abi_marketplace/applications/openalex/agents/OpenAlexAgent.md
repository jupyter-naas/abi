# OpenAlexAgent

## What it is
- A thin wrapper around `IntentAgent` that defines an “OpenAlex” agent persona.
- Provides general guidance about OpenAlex (no tools are configured; it does not fetch real OpenAlex data).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory to build and return an `OpenAlexAgent` with:
    - A predefined system prompt (`SYSTEM_PROMPT`)
    - No tools (`tools = []`)
    - A small set of RAW intents for informational responses
    - Optional shared state and configuration (auto-created if not provided)
- `class OpenAlexAgent(IntentAgent)`
  - Concrete agent class; currently adds no behavior beyond `IntentAgent` (inherits everything).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses the chat model imported from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (`model.model` passed as `chat_model`)
- Key constants:
  - `NAME = "OpenAlex"`
  - `DESCRIPTION = "Helps you interact with OpenAlex for academic research and publication data."`
  - `SYSTEM_PROMPT` defines capabilities/constraints (notably: no OpenAlex tools available)

## Usage
```python
from naas_abi_marketplace.applications.openalex.agents.OpenAlexAgent import create_agent

agent = create_agent()

# Then use the agent via IntentAgent's interface (methods depend on IntentAgent implementation).
# Example (placeholder): agent.run("What is OpenAlex?")
```

## Caveats
- No OpenAlex tools are configured (`tools = []`), so the agent cannot retrieve or search real publication/author data.
- The defined intents are informational and explicitly state tool access is unavailable.

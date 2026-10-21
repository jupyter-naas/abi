# PennylaneAgent

## What it is
- A thin wrapper around the core `Agent` abstraction that wires in the Pennylane integration tools and a predefined system prompt.
- Factory function `create_agent()` builds and returns a ready-to-use `PennylaneAgent`.

## Public API
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> PennylaneAgent`
  - Creates a `PennylaneAgent` configured with:
    - Chat model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
    - Tools: Pennylane integration tools via `as_tools(...)`
    - Defaults:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided
      - `AgentSharedState(thread_id="0")` if not provided
      - `MemorySaver()` for memory

- `class PennylaneAgent(Agent)`
  - No additional methods/attributes; inherits behavior from `naas_abi_core.services.agent.Agent.Agent`.

## Configuration/Dependencies
- Environment/configuration:
  - Uses `ABIModule.get_instance().configuration.pennylane_api_token` to build the integration configuration:
    - `PennylaneIntegrationConfiguration(api_key=pennylane_api_token)`
- Key imports:
  - Core agent framework: `naas_abi_core.services.agent.Agent` (`Agent`, `AgentConfiguration`, `AgentSharedState`, `MemorySaver`)
  - Pennylane integration: `naas_abi_marketplace.applications.pennylane.integrations.PennylaneIntegration.as_tools`
  - Chat model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
- Constants:
  - `NAME`, `DESCRIPTION`, `MODEL`, `TEMPERATURE`, `AVATAR_URL`, `SYSTEM_PROMPT`
  - Note: `MODEL` and `TEMPERATURE` are defined but not used in `create_agent()`.

## Usage
```python
from naas_abi_marketplace.applications.pennylane.agents.PennylaneAgent import create_agent

agent = create_agent()

# Interact using the base Agent interface (methods depend on naas_abi_core Agent implementation)
# e.g., agent.run(...) / agent.invoke(...) as supported by the Agent class.
```

## Caveats
- If `pennylane_api_token` is missing/invalid, the Pennylane tools may not function (the system prompt instructs users to configure `PENNYLANE_API_TOKEN` in `.env`).
- The exact interaction methods (e.g., `run`, `invoke`) are not defined here; they come from the inherited `Agent` class.

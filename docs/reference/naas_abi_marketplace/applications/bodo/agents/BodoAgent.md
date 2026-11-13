# BodoAgent

## What it is
- A specialized `Agent` configured to act as a data analysis assistant for **Bodo DataFrames** (`bodo.pandas`).
- Bundles:
  - A fixed system prompt that instructs Bodo/pandas-style analysis behavior.
  - A default chat model from the application’s model registry.
  - No code runner of its own: analysis scripts run in the caller's coding workspace, through the default workspace tools (`write_file`, `run_terminal`), which exist only when a coding workspace is bound to the conversation.

## Public API
- `class BodoAgent(Agent)`
  - Agent subclass with predefined class attributes:
    - `name = "BodoAgent"`
    - `description = "An agent that can analyze large data with Bodo DataFrames"`
    - `avatar_url = "<Naas logo URL>"`
    - `system_prompt`: instructions to use `import bodo.pandas as pd`, run safe local analysis, and summarize findings.
    - `suggestions`: UI-style suggestion list (currently includes “Summarize CSV”).

- `BodoAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> BodoAgent` (classmethod)
  - Creates and returns a configured `BodoAgent`.
  - Behavior:
    - Gets the application singleton: `ABIModule.get_instance()`
    - Retrieves the default chat model via `abi_module.engine.services.model_registry.get_default_chat_model()`
    - Attaches no tool of its own (the agent's default workspace tools act on the caller's coding workspace)
    - Defaults:
      - `AgentConfiguration(system_prompt=cls.system_prompt)` if `agent_configuration` is `None`
      - `AgentSharedState(thread_id="0")` if `agent_shared_state` is `None`

## Configuration/Dependencies
- Imports / dependencies:
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - Application module (imported inside `New`):
    - `naas_abi_marketplace.applications.bodo.ABIModule` (singleton access)
- Requires a working model registry:
  - `abi_module.engine.services.model_registry` must be initialized (asserted).

## Usage
```python
from naas_abi_marketplace.applications.bodo.agents.BodoAgent import BodoAgent

agent = BodoAgent.New()

# Interacting with the agent (sending messages, running tools) depends on
# the naas_abi_core Agent runtime used in your environment.
```

## Caveats
- `BodoAgent.New()` asserts that the model registry service is initialized; otherwise it raises an `AssertionError`.
- Without a coding workspace bound to the conversation, the agent cannot run anything and says so.

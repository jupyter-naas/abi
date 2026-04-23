# NebariAgent

## What it is
A thin wrapper around `naas_abi_core.services.agent.IntentAgent.IntentAgent` that builds an intent-driven agent preconfigured to answer Nebari platform questions using a predefined system prompt and a fixed set of raw Q&A intents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Creates and returns a configured `NebariAgent` instance.
  - Sets defaults when arguments are not provided:
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
    - `AgentSharedState(thread_id="0")`
  - Loads the chat model from `naas_abi_marketplace.applications.nebari.models.default`.
  - Attaches:
    - `intents`: a list of `Intent` entries (mostly `IntentType.RAW`) covering Nebari architecture, deployment, features, security, scaling, and community.
    - `tools`: empty list
    - `agents`: empty list
    - `memory`: `None`

- `class NebariAgent(IntentAgent)`
  - No additional methods or overrides; inherits all behavior from `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires an application-provided model:
  - `from naas_abi_marketplace.applications.nebari.models.default import model`
- Built-in constants:
  - `NAME`, `DESCRIPTION`, `AVATAR_URL`, `SYSTEM_PROMPT`, `SUGGESTIONS` (currently empty)

## Usage
```python
from naas_abi_marketplace.applications.nebari.agents.NebariAgent import create_agent

agent = create_agent()
# Use `agent` via the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No tools, sub-agents, or memory are configured (`tools=[]`, `agents=[]`, `memory=None`).
- The agent behavior is driven primarily by the imported chat model and the static RAW intents defined in this module.

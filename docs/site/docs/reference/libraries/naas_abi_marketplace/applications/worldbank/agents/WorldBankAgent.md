# WorldBankAgent

## What it is
A minimal `IntentAgent` implementation that provides general guidance about World Bank data and indicators. It does **not** include any World Bank tools or data retrieval capabilities.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that constructs and returns a configured `WorldBankAgent`.
  - Sets:
    - `name`: `"WorldBank"`
    - `description`: guidance-focused description
    - `system_prompt`: instructs the agent to provide general information only
    - `tools`: `[]` (no tools)
    - `intents`: two RAW intents for feature overview and indicator explanations
    - `state`: provided or new `AgentSharedState`
    - `configuration`: provided or new `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
    - `memory`: `None`

- `class WorldBankAgent(IntentAgent)`
  - Concrete agent class with no additional behavior beyond `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Uses chat model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (`model.model` is passed as `chat_model`)
- Key module constants:
  - `SYSTEM_PROMPT`: emphasizes no tool access and guidance-only behavior
  - `SUGGESTIONS`: empty list (currently unused)

## Usage
```python
from naas_abi_marketplace.applications.worldbank.agents.WorldBankAgent import create_agent

agent = create_agent()
# Use agent according to the IntentAgent interface provided by naas_abi_core
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot retrieve or query real World Bank data.
- Intended output is guidance and explanations only; it should acknowledge lack of tool access per `SYSTEM_PROMPT`.

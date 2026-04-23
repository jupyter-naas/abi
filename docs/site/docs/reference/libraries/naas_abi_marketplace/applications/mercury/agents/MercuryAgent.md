# MercuryAgent

## What it is
- An `IntentAgent` implementation configured to provide general guidance about Mercury (banking/financial operations).
- Ships with a system prompt and two simple RAW intents.
- No Mercury tools are configured (tools list is empty).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that returns a configured `MercuryAgent`.
  - Sets:
    - `name`: `"Mercury"`
    - `description`: `"Helps you interact with Mercury for banking and financial operations."`
    - `chat_model`: imported from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`
    - `tools`: `[]` (none)
    - `intents`: two `Intent` entries of type `IntentType.RAW`
    - `configuration`: defaults to `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided
    - `state`: uses provided `AgentSharedState` or creates a new one
    - `memory`: `None`
- `class MercuryAgent(IntentAgent)`
  - Concrete agent class (no additional behavior; inherits everything from `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Uses GPT model wrapper from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (imports `model` and passes `model.model`)
- Key constants:
  - `SYSTEM_PROMPT`: instructs the agent to provide guidance only and explicitly states tools are unavailable.
  - `SUGGESTIONS`: defined as empty list (not used in this module).

## Usage
```python
from naas_abi_marketplace.applications.mercury.agents.MercuryAgent import create_agent

agent = create_agent()
# Interactions depend on the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot access Mercury accounts, balances, or execute operations; it can only provide general information and guidance as described in `SYSTEM_PROMPT`.

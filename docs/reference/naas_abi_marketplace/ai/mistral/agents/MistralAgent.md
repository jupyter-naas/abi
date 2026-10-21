# MistralAgent

## What it is
A thin wrapper around `naas_abi_core`’s `IntentAgent` configured for a Mistral chat model and a predefined system prompt, exposing a small set of coding/documentation-related intents.

## Public API

- **Constants**
  - `AVATAR_URL`: Avatar image URL.
  - `NAME`: `"Mistral"`.
  - `DESCRIPTION`: Description of the agent/model.
  - `SYSTEM_PROMPT`: System prompt defining behavior and self-recognition rules.
  - `SUGGESTIONS`: Empty list.

- **Functions**
  - `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
    - Builds and returns a configured `MistralAgent`.
    - Retrieves chat model via `ABIModule.get_instance().engine.services.model_registry.get_chat_model("mistral-medium-2508")`.
    - Registers intents (all `IntentType.AGENT`, target `"call_model"`):
      - `"generate code"`, `"review code"`, `"optimize code"`, `"document technical details"`, `"help with programming"`.
    - Defaults:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided.
      - `AgentSharedState(thread_id="0")` if not provided.
    - Passes `tools=[]`, `agents=[]`, `memory=None`.

- **Classes**
  - `class MistralAgent(IntentAgent)`
    - No overrides; inherits all behavior from `IntentAgent`.

## Configuration/Dependencies
- **Core dependencies**
  - `naas_abi_core.services.agent.IntentAgent`: `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`.
- **Runtime dependency**
  - `naas_abi_marketplace.ai.mistral.ABIModule` to resolve the chat model:
    - `model_registry.get_chat_model("mistral-medium-2508")`.

## Usage
```python
from naas_abi_marketplace.ai.mistral.agents.MistralAgent import create_agent

agent = create_agent()
# Interact with `agent` through the IntentAgent interface provided by `naas_abi_core`.
```

## Caveats
- `MistralAgent` contains no custom logic; behavior depends on `IntentAgent` and the resolved chat model.
- All intents target `"call_model"`; routing/execution is handled by `IntentAgent`.

# ZettafoxAgent

## What it is
- A thin `Agent` subclass that wires a predefined chat model (`qwen-3.6`) and default configuration/state for the Zettafox module.

## Public API
- `class ZettafoxAgent(Agent)`
  - Class attributes:
    - `name`: Human-readable agent name.
    - `description`: Short description.
    - `system_prompt`: Default system prompt used when creating the agent.
    - `logo_url`: Path to the agent logo asset.
  - `@staticmethod get_model() -> ChatModel`
    - Returns the chat model named `"qwen-3.6"` from the Zettafox `ABIModule` model registry.
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> ZettafoxAgent`
    - Factory constructor that:
      - Creates default `AgentConfiguration(system_prompt=cls.system_prompt)` if none provided.
      - Creates default `AgentSharedState()` if none provided.
      - Instantiates `ZettafoxAgent` with empty `tools` and `agents`, `memory=None`, and the model from `get_model()`.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `ChatModel`
- Depends on `naas_abi_marketplace.ai.zettafox.ABIModule`:
  - Must provide `ABIModule.get_instance().engine.services.model_registry.get_chat_model(...)`.
- Model name is hard-coded to `"qwen-3.6"`.

## Usage
```python
from naas_abi_marketplace.ai.zettafox.agents.ZettafoxAgent import ZettafoxAgent

agent = ZettafoxAgent.New()
# agent is an initialized Agent with the "qwen-3.6" chat model and default system prompt
```

## Caveats
- `tools` and nested `agents` are always initialized as empty lists in `New()`.
- `memory` is always set to `None` in `New()`.
- `get_model()` will fail if the Zettafox `ABIModule` instance/engine/model registry is not available or if `"qwen-3.6"` is not registered.

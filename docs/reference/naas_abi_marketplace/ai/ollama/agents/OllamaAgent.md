# OllamaAgent

## What it is
`OllamaAgent` is an `Agent` implementation configured as a local, offline assistant backed by the Ollama chat model `"qwen-2.5-3b"`. It provides a predefined system prompt, branding metadata, and disables default tools to keep the “no tools / no network” runtime behavior consistent with its prompt.

## Public API
- **Class `OllamaAgent(Agent)`**
  - **Class attributes (metadata)**
    - `name`: Display name (`"Ollama"`).
    - `description`: Human-readable description of the agent.
    - `avatar_url`: URL to an avatar image.
    - `system_prompt`: Markdown-oriented system prompt describing offline/local constraints and behavior.
    - `suggestions`: List of UI-style suggestion dicts (label/value/description).
  - **`@classmethod New(agent_shared_state=None, agent_configuration=None) -> OllamaAgent`**
    - Factory constructor that:
      - Resolves a chat model from the marketplace module registry (`"qwen-2.5-3b"`).
      - Creates default `AgentConfiguration(system_prompt=...)` when none provided.
      - Creates default `AgentSharedState(thread_id="0")` when none provided.
      - Instantiates `Agent` with:
        - `tools=[]`, `agents=[]`, `memory=None`
        - `enable_default_tools=False`

## Configuration/Dependencies
- Depends on core agent classes:
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
- Depends on the marketplace Ollama module singleton and its model registry:
  - `naas_abi_marketplace.ai.ollama.ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry.get_chat_model("qwen-2.5-3b")`
- Important configuration behavior:
  - If `agent_configuration` is not passed, it is created with `system_prompt=OllamaAgent.system_prompt`.
  - Default tools are explicitly disabled via `enable_default_tools=False`.

## Usage
```python
from naas_abi_marketplace.ai.ollama.agents.OllamaAgent import OllamaAgent

agent = OllamaAgent.New()
# agent is now configured with the "qwen-2.5-3b" chat model and no default tools enabled.
```

## Caveats
- `New()` requires the Ollama marketplace module (`ABIModule`) and its engine/model registry to be properly initialized in the environment; otherwise model lookup can fail.
- Although the underlying model may support tool calling, this agent is instantiated with `tools=[]` and `enable_default_tools=False`.

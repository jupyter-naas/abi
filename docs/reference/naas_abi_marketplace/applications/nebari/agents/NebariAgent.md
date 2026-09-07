# NebariAgent

## What it is
An `IntentAgent` specialization that builds a Nebari-focused agent preconfigured with a Nebari system prompt and a fixed set of RAW Q&A intents.

## Public API
- `class NebariAgent(IntentAgent)`
  - Purpose: Provide a ready-to-use intent-driven agent for answering questions about the Nebari open-source data science platform.
  - Class attributes:
    - `name`: `"Nebari"`
    - `description`: expert agent description
    - `avatar_url`: static image URL
    - `system_prompt`: Nebari-focused system prompt
    - `suggestions`: empty list
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> NebariAgent`
    - Creates and returns a configured `NebariAgent`.
    - Loads models from `ABIModule.get_instance().engine.services.model_registry`:
      - `chat_model = registry.get_default_chat_model()`
      - `embedding_model = registry.get_default_embedding_model().model`
    - Configures:
      - `tools = []`
      - `agents = []`
      - `intents`: a static list of `Intent(..., intent_type=IntentType.RAW, intent_target=...)` covering Nebari overview, architecture, deployment, features, workflows, ecosystem, scaling/cost, security, and community.
      - `memory = None`
    - Defaults:
      - `agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)` if not provided
      - `agent_shared_state = AgentSharedState(thread_id="0")` if not provided

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires Nebari application module:
  - `from naas_abi_marketplace.applications.nebari import ABIModule`
- Requires `ModelRegistryService` to be initialized:
  - `registry` is asserted non-`None` (`"ModelRegistryService not initialized"`)

## Usage
```python
from naas_abi_marketplace.applications.nebari.agents.NebariAgent import NebariAgent

agent = NebariAgent.New()
# Interact with `agent` using the IntentAgent interface from naas_abi_core.
```

## Caveats
- No tools, sub-agents, or memory are configured (`tools=[]`, `agents=[]`, `memory=None`).
- Instantiation requires a configured Nebari `ABIModule` engine with an initialized `model_registry`; otherwise an assertion error is raised.

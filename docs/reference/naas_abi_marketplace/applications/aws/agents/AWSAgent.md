# AWSAgent

## What it is
- An `IntentAgent` specialization for answering general Amazon Web Services (AWS) questions.
- Provides guidance only:
  - Explicitly states it has **no AWS tool access**.
  - Ships with a fixed `system_prompt`, empty `tools`, and a couple of predefined RAW intents.

## Public API
- `class AWSAgent(IntentAgent)`
  - Agent definition with class attributes:
    - `name = "AWS"`
    - `description = "Helps you interact with Amazon Web Services for cloud infrastructure and services."`
    - `system_prompt` (guidance-only, no tool access)
    - `suggestions = []`

- `AWSAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> AWSAgent`
  - Class factory that constructs an `AWSAgent` instance.
  - Behavior:
    - Fetches default chat and embedding models from the application `ModelRegistryService`.
    - Initializes:
      - `tools = []`
      - `intents` with two `IntentType.RAW` entries (AWS services info; infrastructure/resource management)
    - Defaults:
      - `agent_configuration = AgentConfiguration(system_prompt=AWSAgent.system_prompt)` if not provided
      - `agent_shared_state = AgentSharedState(thread_id="0")` if not provided
    - Returns `AWSAgent(..., memory=None)`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Depends on AWS application module singleton:
  - `naas_abi_marketplace.applications.aws.ABIModule.get_instance()`
  - Uses `abi_module.engine.services.model_registry`:
    - `get_default_chat_model()`
    - `get_default_embedding_model().model`
- Configuration input:
  - `AgentConfiguration(system_prompt=...)` controls the agent’s operating constraints (guidance only).

## Usage
```python
from naas_abi_marketplace.applications.aws.agents.AWSAgent import AWSAgent

agent = AWSAgent.New()

# Use `agent` with your IntentAgent runtime/orchestrator.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot access or modify AWS resources; it only provides general information and guidance.
- Requires the AWS `ABIModule` engine and its `model_registry` service to be initialized; otherwise an assertion will fail.

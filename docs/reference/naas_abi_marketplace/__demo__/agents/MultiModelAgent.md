# MultiModelAgent

## What it is
A demo **multi-model** agent that orchestrates several sub-agents (each backed by a different canonical model), then calls a comparison agent to summarize pros/cons. It also includes an optional Python code execution sub-agent exposed via workflow tools.

## Public API

- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> Agent`
  - Builds and returns a configured `MultiModelAgent` with:
    - Main chat model: `CanonicalModelId.GPT_5_2`
    - Sub-agents (passed as `tools`):
      - `gpt-5.2_agent` (`GPT_5_2`)
      - `gpt-5-mini_agent` (`GPT_5_MINI`)
      - `gpt-5.5_agent` (`GPT_5_5`)
      - `comparison_agent` (`GPT_5_MINI`)
      - `python_code_execution_agent` (`GPT_5_MINI`, with tools from `ExecutePythonCodeWorkflow.as_tools()`)
    - Defaults:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided
      - `AgentSharedState(thread_id="0")` if not provided

- `class MultiModelAgent(naas_abi_core.services.agent.Agent.Agent)`
  - `as_api(router: fastapi.APIRouter, route_name: str = NAME, name: str = ..., description: str = ..., description_stream: str = ..., tags: Optional[list[str | Enum]] = None) -> None`
    - Exposes the agent as FastAPI endpoints by delegating to `Agent.as_api(...)`.
    - Applies demo-friendly defaults for route/name/descriptions.

## Configuration/Dependencies

- Runtime dependencies (used directly in this module):
  - `naas_abi.ABIModule` (expects `ABIModule.get_instance().engine.services.model_registry`)
  - `naas_abi_core.models.Model.CanonicalModelId` (model identifiers)
  - `naas_abi_core.services.agent.Agent` (`Agent`, `AgentConfiguration`, `AgentSharedState`)
  - `naas_abi_marketplace.__demo__.workflows.ExecutePythonCodeWorkflow` (`ExecutePythonCodeWorkflow`, `ExecutePythonCodeWorkflowConfiguration`)
  - `fastapi.APIRouter`

- Module constants:
  - `NAME = "Multi_Models"`
  - `MODEL = CanonicalModelId.GPT_5_2` (declared but not used by `create_agent`)
  - `TEMPERATURE = None` (declared but not used here)
  - `SYSTEM_PROMPT` (orchestration instructions and formatting constraints)
  - `SUGGESTIONS` (example prompts; not used programmatically in this file)
  - `AVATAR_URL`, `DESCRIPTION` (used as metadata)

## Usage

### Create the agent
```python
from naas_abi_marketplace.__demo__.agents.MultiModelAgent import create_agent

agent = create_agent()
```

### Expose as FastAPI endpoints
```python
from fastapi import FastAPI, APIRouter
from naas_abi_marketplace.__demo__.agents.MultiModelAgent import create_agent

app = FastAPI()
router = APIRouter()

agent = create_agent()
agent.as_api(router)

app.include_router(router)
```

## Caveats

- `create_agent()` requires a working `ABIModule` singleton with a configured `model_registry` that supports `registry.get_chat_model(model_id)`.
- The Python execution capability is enabled by attaching tools from `ExecutePythonCodeWorkflow`; execution behavior and safety depend on that workflow and the sub-agent prompt.
- `MODEL` and `TEMPERATURE` constants are not used by `create_agent()` in this module.

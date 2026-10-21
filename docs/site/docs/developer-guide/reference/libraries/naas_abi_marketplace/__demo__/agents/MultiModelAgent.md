# MultiModelAgent

## What it is
A demo agent factory and subclass that builds a **multi-model LangChain/OpenAI-backed agent** composed of several sub-agents (different OpenAI models), a comparison agent, and an optional Python code execution agent (via a workflow exposed as tools).

## Public API

- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> Agent`
  - Constructs and returns a `MultiModelAgent` preconfigured with:
    - A primary chat model (`o3-mini`)
    - A set of sub-agents:
      - `o3-mini_agent`
      - `gpt-4o-mini_agent`
      - `gpt-4-1_agent`
      - `comparison_agent`
      - `python_code_execution_agent` (with tools from `ExecutePythonCodeWorkflow`)
    - Default `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided
    - Default `AgentSharedState(thread_id="0")` if not provided

- `class MultiModelAgent(naas_abi_core.services.agent.Agent.Agent)`
  - `as_api(router: fastapi.APIRouter, route_name: str = NAME, name: str = ..., description: str = ..., description_stream: str = ..., tags: Optional[list[str | Enum]] = None) -> None`
    - Thin wrapper over `Agent.as_api(...)` to expose API endpoints on a FastAPI router.
    - Defaults route/name/description values for this demo agent.

## Configuration/Dependencies

- Environment/Secrets:
  - Requires `OPENAI_API_KEY` available via `naas_abi.secret.get("OPENAI_API_KEY")`.

- Key dependencies:
  - `fastapi.APIRouter`
  - `langchain_openai.ChatOpenAI`
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_marketplace.__demo__.workflows.ExecutePythonCodeWorkflow`:
    - `ExecutePythonCodeWorkflow`, `ExecutePythonCodeWorkflowConfiguration`
  - `pydantic.SecretStr`

- Built-in constants (used as defaults):
  - `NAME = "Multi_Models"`
  - `MODEL = "o3-mini"` (note: constant exists; the factory hardcodes model strings)
  - `SYSTEM_PROMPT` instructs orchestration across sub-agents and comparison agent, and directs Python execution via the Python execution agent.

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

- Requires a valid OpenAI API key retrievable via `secret.get("OPENAI_API_KEY")`.
- The Python execution capability is enabled by attaching tools from `ExecutePythonCodeWorkflow`; execution behavior and safety constraints depend on that workflow and the system prompt used by `python_code_execution_agent`.
- The `MODEL` and `TEMPERATURE` module constants are not used by `create_agent()`; model names and temperature are hardcoded in `ChatOpenAI(...)` initializations.

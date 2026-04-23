# BodoAgent

## What it is
- A thin wrapper around `naas_abi_core.services.agent.Agent.Agent` configured as a data analysis assistant specialized for **Bodo DataFrames** (`bodo.pandas`).
- Provides a factory function that assembles the agent with:
  - A predefined system prompt
  - A ChatGPT model (`gpt_4_1_mini`)
  - A Python execution tool workflow

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Agent`
  - Creates and returns a configured `BodoAgent`.
  - Defaults:
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided
    - `AgentSharedState(thread_id="0")` if not provided
  - Attaches tools from `ExecutePythonCodeWorkflow` with:
    - `timeout=600`
    - `allow_imports=True`

- `class BodoAgent(Agent)`
  - Subclass of `Agent` with no additional behavior (`pass`).

## Configuration/Dependencies
- Core dependencies (imported):
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - Model:
    - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
  - Tooling:
    - `naas_abi_marketplace.__demo__.workflows.ExecutePythonCodeWorkflow`:
      - `ExecutePythonCodeWorkflow`, `ExecutePythonCodeWorkflowConfiguration`
- Built-in constants:
  - `NAME = "BodoAgent"`
  - `DESCRIPTION = "An agent that can analyze large data with Bodo DataFrames"`
  - `AVATAR_URL = ".../Naas.png"`
  - `SYSTEM_PROMPT`: instructs the agent to use `import bodo.pandas as pd` and pandas-style APIs, avoid unsafe/network ops, and summarize results after execution.
  - `SUGGESTIONS`: includes `"Summarize CSV"` example prompt.

## Usage
```python
from naas_abi_marketplace.applications.bodo.agents.BodoAgent import create_agent

agent = create_agent()

# The returned object is an Agent (BodoAgent) configured with a Python execution tool.
# How you run/send messages depends on the Agent framework used by naas_abi_core.
```

## Caveats
- `BodoAgent` adds no methods beyond the base `Agent`; behavior comes from the base class plus provided configuration/tools.
- The attached execution tool is configured with `allow_imports=True` and a 600-second timeout.

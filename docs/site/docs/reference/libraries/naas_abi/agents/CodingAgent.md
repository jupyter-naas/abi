# CodingAgent

## What it is
- A `CodingAgent` implementation backed by an `OpencodeAgent` server.
- Configured to operate within the `naas_abi` module working directory and guided by a fixed system prompt.

## Public API
- `class CodingAgent(OpencodeAgent)`
  - Agent specialization with:
    - `name = "CodingAgent"`
    - `description = "Coding agent backed by an opencode server for the naas_abi module."`
    - `system_prompt` set to the module’s `SYSTEM_PROMPT`
- `CodingAgent.New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[dict] = None) -> CodingAgent`
  - Factory constructor that:
    - Sets `workdir` to the `naas_abi` module root (two levels above this file).
    - Reads optional configuration from environment variables:
      - `NAAS_ABI_CODING_AGENT_PORT` → `port` (int) or `None` if unset/blank
      - `NAAS_ABI_CODING_AGENT_MODEL` → `model` (defaults to `"openai/gpt-5.3-codex"`)
    - Ignores `agent_configuration` (explicitly deleted).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent.AgentSharedState`
  - `naas_abi_core.services.agent.OpencodeAgent.OpencodeAgent`
  - `naas_abi_core.services.agent.OpencodeAgent.OpencodeAgentConfiguration`
- Environment variables:
  - `NAAS_ABI_CODING_AGENT_PORT`: optional port for the opencode server (string parsed to `int`).
  - `NAAS_ABI_CODING_AGENT_MODEL`: optional model identifier; default `"openai/gpt-5.3-codex"`.

## Usage
```python
from naas_abi.agents.CodingAgent import CodingAgent

agent = CodingAgent.New()
```

With environment overrides:
```python
import os
from naas_abi.agents.CodingAgent import CodingAgent

os.environ["NAAS_ABI_CODING_AGENT_PORT"] = "8080"
os.environ["NAAS_ABI_CODING_AGENT_MODEL"] = "openai/gpt-5.3-codex"

agent = CodingAgent.New()
```

## Caveats
- `agent_configuration` passed to `New()` is ignored.
- `NAAS_ABI_CODING_AGENT_PORT` must be a valid integer if set; otherwise `int(...)` will raise `ValueError`.

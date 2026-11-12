# CodingAgent

## What it is
- The "OpenCode Coding" agent: an `OpencodeAgent` that talks to the OpenCode server of the caller's own coding sandbox.
- Off by default: it is a `naas_abi` module agent only when the module configuration sets `opencode_coding_agent: true`.
- It never starts OpenCode on the API host. Without a coding sandbox bound to the conversation (`coding_harness_base`), `start()` raises `OpencodeStartupError`.

## Public API
- `class CodingAgent(OpencodeAgent)`
  - `name = "OpenCode Coding"`
  - `enabled_by = "opencode_coding_agent"`: the module configuration flag that loads it (`ModuleAgentLoader`).
- `CodingAgent.New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[dict] = None) -> CodingAgent`
  - Ignores `agent_configuration`.
- `_base_url`: the bound sandbox's OpenCode server.
- `start()`: checks that the sandbox's server answers `/global/health`; starts nothing.

## Configuration

```yaml
modules:
  - module: naas_abi
    config:
      opencode_coding_agent: true
```

## Usage
```python
from naas_abi.agents.CodingAgent import CodingAgent
from naas_abi_core.services.agent.context import coding_harness_base

coding_harness_base.set("http://<sandbox harness>")
agent = CodingAgent.New()
```

## Caveats
- OpenCode permission requests are refused (`OpencodeAgent`): nothing is granted on the user's behalf.

# `agents/` — AGENTS.md

> Scope: agent definitions for the `{{module_name_snake}}` module. See the module's [AGENTS.md](../AGENTS.md) for module-wide context.

## What goes here

`Agent` (or `IntentAgent`) subclasses that bind a chat model to tools and sub-agents. Each agent file is a self-contained, registerable unit.

## File shape

Files are `PascalCase`, one agent per file: `<Name>Agent.py`.

```python
from typing import Optional
from naas_abi_core.services.agent.Agent import (
    Agent, AgentConfiguration, AgentSharedState,
)

NAME = "<Name>Agent"
DESCRIPTION = "..."
SYSTEM_PROMPT = """You are <Name>Agent..."""

class <Name>Agent(Agent):
    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "<Name>Agent":
        from naas_abi_marketplace.ai.chatgpt.models.gpt_5 import model as chatgpt_model

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()

        return cls(
            name=NAME,
            description=DESCRIPTION,
            chat_model=chatgpt_model.model,
            tools=[],
            agents=[],
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
```

## Conventions

- **Module-level constants** at the top: `NAME`, `DESCRIPTION`, `SYSTEM_PROMPT`. Add `SLUG`, `TYPE`, `AVATAR_URL`, `MODEL`, `INTENTS` when the agent is user-facing (catalog-discoverable).
- **`.New(...)` classmethod factory** — never instantiate the agent directly elsewhere; always go through `.New(...)` so shared state and configuration are wired consistently.
- **Tools bind to integrations**, not to raw HTTP. Import an `Integration` from `../integrations/` and expose its methods as tools via `as_tools()`.
- **Sub-agents** go in the `agents=[]` list — useful for coordinator / supervisor topologies (see `IntentAgent` and `CoordinatorAgent` in core).

## Scaffold a new agent

```bash
abi new agent <name> .
```

This drops `<Name>Agent.py` into this directory using the standard template.

## Tests

Colocated as `<Name>Agent_test.py`:

```python
import pytest
from {{module_name_snake}}.agents.<Name>Agent import <Name>Agent

@pytest.fixture
def agent():
    return <Name>Agent.New()

def test_basic_invocation(agent):
    result = agent.invoke("ping")
    assert result is not None
```

Run:

```bash
uv run pytest {{module_name_snake}}/agents
uv run pytest {{module_name_snake}}/agents/<Name>Agent_test.py -v
```

## Wiring into the module

If the agent is meant to be discovered by the engine / coordinator, expose it from `agents/__init__.py` or register it under `INTENTS` in a coordinator agent. Cross-module registration goes through `ABIModule.dependencies` — see the module's [AGENTS.md](../AGENTS.md).

## See also

- Core agent service (constructor args, streaming, memory, checkpointing): [`.abi/libs/naas-abi-core/.../services/agent/AGENTS.md`](../../../.abi/libs/naas-abi-core/naas_abi_core/services/agent/AGENTS.md)
- Model registry (canonical model ids): [`.abi/libs/naas-abi-core/.../services/model_registry/AGENTS.md`](../../../.abi/libs/naas-abi-core/naas_abi_core/services/model_registry/AGENTS.md)
- Reference scaffolds: [`.abi/libs/naas-abi-marketplace/.../__demo__/agents/MultiModelAgent.py`](../../../.abi/libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/agents/MultiModelAgent.py)

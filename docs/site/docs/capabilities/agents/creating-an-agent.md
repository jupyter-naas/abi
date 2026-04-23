# Creating an Agent

ABI agents use the `Agent.New()` class method pattern. The agent is self-contained: name, system prompt, tools, and intent registration are all in one place.

---

## The pattern

Every agent:
1. Extends `AbiAgent` (from `naas_abi.agents.AbiAgent`).
2. Exposes a `New(...)` classmethod as its canonical constructor.
3. Declares its intents via `IntentConfiguration`.
4. Lists its tools (workflows, integrations, or other agents).

```python
# agents/MyAgent.py
from naas_abi.agents.AbiAgent import AbiAgent, AbiAgentConfiguration
from naas_abi_core.services.agent.Agent import AgentSharedState, IntentConfiguration
from naas_abi_core.models.Model import ChatModel

class MyAgent(AbiAgent):

    @classmethod
    def New(
        cls,
        model: ChatModel,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AbiAgentConfiguration | None = None,
    ) -> "MyAgent":
        name = "My Agent"
        description = "Handles queries about [your domain]."
        system_prompt = f"""
You are {name}. Your role is to [describe the role].

You have access to the following tools:
- [list key tools]

Always be concise, factual, and grounded in the data available to you.
"""
        intents = [
            IntentConfiguration(
                name="handle_domain_query",
                description="Handle queries about [your domain]",
                scope="supervisor",  # or "integration" or "research"
            )
        ]

        tools = [
            # Add your workflow and integration tools here
        ]

        if agent_configuration is None:
            agent_configuration = AbiAgentConfiguration(
                system_prompt=system_prompt,
                intents=intents,
            )
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id=0)

        return cls(
            name=name,
            description=description,
            chat_model=model,
            tools=tools,
            agents=[],  # Sub-agents this agent can delegate to
            state=agent_shared_state,
            configuration=agent_configuration,
        )
```

---

## Adding tools from workflows

Workflows expose themselves as tools via `as_tools()`. Add them to your agent's tool list:

```python
from naas_abi.modules.custom.my_module.workflows.MyWorkflow import (
    MyWorkflow,
    MyWorkflowConfiguration,
)

# ... inside New():
my_workflow = MyWorkflow(MyWorkflowConfiguration(
    integration_config=MyIntegrationConfiguration(
        api_key=secret.get("MY_API_KEY")
    )
))
tools = my_workflow.as_tools()
```

---

## Adding tools from integrations

Integrations expose themselves as tools directly:

```python
from naas_abi.modules.custom.my_module.integrations.MyIntegration import (
    MyIntegration,
    MyIntegrationConfiguration,
)

# ... inside New():
if secret.get("MY_API_KEY"):
    config = MyIntegrationConfiguration(api_key=secret.get("MY_API_KEY"))
    tools += MyIntegration.as_tools(config)
```

---

## Using an agent as a tool in another agent

Pass agents in the `agents=[]` list:

```python
from naas_abi.agents.OntologyEngineerAgent import OntologyEngineerAgent

# ... inside New():
ontology_agent = OntologyEngineerAgent.New(model=model)

return cls(
    name=name,
    ...
    agents=[ontology_agent],   # MyAgent can now delegate to OntologyEngineerAgent
)
```

---

## Intent scopes

| Scope | When to use |
|-------|------------|
| `supervisor` | The agent handles general user queries. The supervisor will route to it. |
| `integration` | The agent requires live API credentials. Available for direct call, not auto-routed. |
| `research` | Experimental agent. Excluded from all routing. |

See [[adr/20250925_intent-scope-agent-routing|ADR: Intent Scope]].

---

## Registering in the module

The Engine auto-discovers agents in `agents/*.py` that expose `Agent.New()`. No explicit registration required if your agent file is inside your module's `agents/` directory.

The Engine calls `Agent.New()` with the configured model at startup.

---

## Persistent memory

Memory is automatic. Set `POSTGRES_URL` in `.env` for persistent cross-session memory:

```bash
POSTGRES_URL=postgresql://abi_user:abi_password@localhost:5432/abi_memory
```

Without it, the agent falls back to in-memory storage (history lost on restart).

---

## REST API exposure

Every agent in the Engine is automatically exposed at:

```http
POST /agents/{agent_route}/completion
POST /agents/{agent_route}/stream-completion
```

Request body:
```json
{
  "prompt": "Your question here",
  "thread_id": 1
}
```

Authentication: `Authorization: Bearer YOUR_API_KEY`.

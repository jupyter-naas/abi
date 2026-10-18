# Creating an Agent

An agent binds a chat model to tools (workflows, integrations) and to other agents. In an in-engine module, an agent is a class with a `New()` class method: the name, system prompt, tools and sub-agents are all in one place, and the engine builds it at startup.

:::tip Remote module?
In a [remote module](/user-guide/build/sdk/build-a-remote-module) an agent is an SDK `IntentAgent` built by an async `create_agent(...)` function and published with an `AgentDescriptor`; `abi new agent` writes that variant when you run it inside a remote module. This page covers the in-engine agent. To choose between the two, see [Creating a Module](/user-guide/build/modules/creating-a-module#remote-or-in-engine).
:::

---

## Scaffold one

From the project root:

```bash
abi new agent Reviewer src/my_module/agents
```

It writes `ReviewerAgent.py`. (Inside a module, `abi new module <name> --in-engine` already scaffolds a first agent.) `abi chat` runs an agent from a terminal:

```bash
abi chat my_module ReviewerAgent    # <module> <agent class name>
```

`abi chat` loads the engine, so in a NATS project it needs the broker (`abi dev up` or `abi stack start`).

---

## The pattern

The scaffold is a subclass of `Agent` (from `naas_abi_core.services.agent.Agent`) with class attributes and a `New(...)` constructor:

```python
# agents/ReviewerAgent.py
from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class ReviewerAgent(Agent):
    name: str = "Reviewer"
    description: str = "Reviews documents and answers questions about them."
    avatar_url: str = "https://example.com/reviewer.png"
    system_prompt: str = """<role>
You are ReviewerAgent, a careful reviewer.
</role>

<objective>
Help the user review their documents.
</objective>

<tools>
[TOOLS]
</tools>

<constraints>
- Only use the provided tools; do not fabricate data.
</constraints>
"""

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "ReviewerAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        # The workspace's default chat model, from the model registry.
        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        tools: list = []   # workflow and integration tools go here
        agents: list = []  # sub-agents this agent can delegate to

        if agent_configuration is None:
            tools_section = "\n".join(f"- {t.name}: {t.description}" for t in tools)
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace("[TOOLS]", tools_section)
            )
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=agents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
```

The model is the registry's default (`services.model_registry.default_chat_model` in `config.yaml`). For a specific model, ask the registry for its canonical id: `registry.get_chat_model("gemma-4-26b-a4b-it")`. A module that needs its own settings reads them from its configuration: `ABIModule.get_instance().configuration`.

The scaffold also has two optional hooks, `onHumanMessage(message)` and `onAImessage(message, agent_name)`, called on every user message and every AI message (also from sub-agents). They are for observation: what they return is ignored, an exception in them is logged and swallowed, and they run inline, so keep them quick.

---

## Routing between agents with `IntentAgent`

`IntentAgent` (from `naas_abi_core.services.agent.IntentAgent`) extends `Agent` with intent mapping: it matches the user's message to intents with an embedding model and routes to the tool or sub-agent the intent names. Most marketplace agents are `IntentAgent`s. They add an `embedding_model` and a list of `Intent` objects:

```python
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from naas_abi_core.services.agent.beta.IntentMapper import Intent, IntentScope, IntentType

INTENTS = [
    Intent(
        intent_value="review a document",
        intent_type=IntentType.TOOL,        # TOOL, AGENT or RAW
        intent_target="review_document",    # the tool or agent name
        intent_scope=IntentScope.DIRECT,    # DIRECT (default is ALL)
    ),
]

# inside New(): embedding_model = registry.get_default_embedding_model().model
return cls(
    name=cls.name,
    description=cls.description,
    chat_model=chat_model,
    embedding_model=embedding_model,
    tools=tools,
    agents=agents,
    intents=INTENTS,
    memory=None,
    state=agent_shared_state,
    configuration=agent_configuration,
)
```

For a complete working example, read an agent of the marketplace, such as `naas_abi_marketplace/applications/github/agents/GitHubAgent.py`.

---

## Adding tools from workflows

Workflows expose themselves as tools with `as_tools()`. Instantiate one with its configuration and add its tools:

```python
from my_module.workflows.MyWorkflow import MyWorkflow, MyWorkflowConfiguration

# ... inside New():
workflow = MyWorkflow(MyWorkflowConfiguration())
tools += workflow.as_tools()
```

See [Creating a Workflow](/user-guide/build/agents/creating-a-workflow).

---

## Adding tools from integrations

By convention an integration module exposes a module-level `as_tools(configuration)` function that returns LangChain tools:

```python
from my_module import ABIModule
from my_module.integrations.MyIntegration import MyIntegrationConfiguration, as_tools

# ... inside New():
api_key = ABIModule.get_instance().configuration.my_api_key
if api_key:
    tools += as_tools(MyIntegrationConfiguration(api_key=api_key))
```

See [Creating an Integration](/user-guide/build/agents/creating-an-integration).

---

## Using an agent as a tool in another agent

Pass agents in the `agents=[]` list:

```python
from naas_abi.agents.OntologyEngineerAgent import OntologyEngineerAgent

# ... inside New():
ontology_agent = OntologyEngineerAgent.New()

return cls(
    name=cls.name,
    ...
    agents=[ontology_agent],   # this agent can now delegate to OntologyEngineerAgent
)
```

---

## Registering in the module

The engine discovers every agent class defined in a module's `agents/*.py` and calls its `New()` at startup (a module-level `create_agent()` function in the file is used as `New` when present). No registration is needed. Make sure the module is listed under `modules:` in `config.yaml`.

---

## Persistent memory

Memory is automatic. When the Engine loads the Document Service (`services.document`
in `config.yaml`; always in NATS mode), agents built with `memory=None` keep their
conversations there, so history survives restarts and appears in the Nexus System
app under the `naas_abi_core.services.agent` namespace.

Outside an Engine (scripts, tests), set `POSTGRES_URL` for persistent memory:

```bash
POSTGRES_URL=postgresql://abi_user:abi_password@localhost:5432/abi_memory
```

Without either, the agent falls back to in-memory storage (history lost on restart).
Memory written by earlier releases to `POSTGRES_URL` moves over with
`abi agent migrate-memory` (a dry run until you add `--apply`).

---

## REST API exposure

Every agent the engine loads is exposed at:

```http
POST /agents/{agent_name}/completion
POST /agents/{agent_name}/stream-completion
```

`{agent_name}` is the agent's `name`, with characters other than letters, digits, `_` and `-` replaced by `_` (`Multi Models` becomes `Multi_Models`).

Request body:
```json
{
  "prompt": "Your question here",
  "thread_id": 1
}
```

Authentication: `Authorization: Bearer YOUR_API_KEY`.

Agents published by [remote modules](/user-guide/build/sdk/build-a-remote-module) have no such route: reach them through Nexus or the chat API (`POST /api/chat/stream`, selecting the agent by its id). See the [REST API](/user-guide/build/applications/api).

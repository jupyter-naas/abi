# AbiAgent

## What it is
A factory and thin wrapper for creating the **Abi** supervisor agent, built on `naas_abi_core.services.agent.IntentAgent`. It configures:
- A system prompt for orchestration behavior
- A small set of tools (including a Knowledge Graph Explorer opener and SPARQL-query-related tools)
- A list of predefined intents for opening local services and routing certain requests to tools

## Public API

### Constants
- `NAME`: `"Abi"`
- `AVATAR_URL`: URL string for the agent avatar
- `DESCRIPTION`: `"Coordinates and manages specialized agents."`
- `SYSTEM_PROMPT`: Supervisor/orchestrator prompt template (contains `[TOOLS]` and `[AGENTS]` placeholders)
- `SUGGESTIONS`: UI-oriented prompt suggestions list

### Functions
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns an `AbiAgent` instance.
  - Configures:
    - Chat model via `naas_abi.models.default.get_model()`
    - Tools:
      - `open_knowledge_graph_explorer` (a LangChain tool returning a localhost link)
      - Tools fetched from the `templatablesparqlquery` module for a fixed set of tool names
    - Shared state (`AgentSharedState(thread_id="0", supervisor_agent=NAME)`) if not provided
    - A set of `Intent` routes (RAW responses for service links; TOOL intents for the KG explorer; a TOOL intent targeting `"get_time"`)
    - Agent configuration by filling `SYSTEM_PROMPT` with formatted tool/agent lists (if not provided)

### Classes
- `class AbiAgent(IntentAgent)`
  - No additional methods/overrides; serves as a named subclass.

## Configuration/Dependencies
- Depends on `naas_abi.models.default.get_model()` to provide the chat model.
- Uses LangChain’s `@tool` decorator: `langchain_core.tools.tool`.
- Requires a loaded `ABIModule` engine module:
  - Looks up `ABIModule.get_instance().engine.modules["naas_abi_core.modules.templatablesparqlquery"]`
  - Asserts it is an instance of `naas_abi_core.modules.templatablesparqlquery.ABIModule`
  - Calls `get_tools([...])` with:
    - `find_business_proposal_agents`
    - `find_coding_agents`
    - `find_math_agents`
    - `find_best_value_agents`
    - `find_fastest_agents`
    - `find_cheapest_agents`
- Localhost service URLs referenced in intents/tools:
  - Oxigraph Explorer: `http://localhost:7878/explorer/`
  - YasGUI: `http://localhost:3000`
  - Dagster: `http://localhost:3001`

## Usage
```python
from naas_abi.agents.AbiAgent import create_agent

agent = create_agent()

# `agent` is an IntentAgent (AbiAgent subclass) configured with tools and intents.
print(agent.name)         # "Abi"
print(agent.description)  # "Coordinates and manages specialized agents."
```

## Caveats
- The sub-agent list is currently empty (`agents: list = []`), so no specialized agents are actually attached by this module (the prior dynamic loading logic is commented out).
- One intent targets the tool name `"get_time"`, but this file does not define it; availability depends on the broader runtime/tooling environment.
- `create_agent()` assumes `ABIModule.get_instance()` is initialized and its engine has the `templatablesparqlquery` module; otherwise it will fail (including via the `assert`).

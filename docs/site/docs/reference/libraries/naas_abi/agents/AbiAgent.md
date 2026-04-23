# `AbiAgent`

## What it is
- `AbiAgent` is a supervisor/orchestrator agent built on `naas_abi_core`’s `IntentAgent`.
- It discovers available sub-agents from the running `ABIModule` engine, builds “intents” to route requests to them, and exposes a small set of SPARQL-based recommendation tools.

## Public API
### Class: `AbiAgent(IntentAgent)`
Operator-facing entry point for creating the orchestrator agent.

#### Class attributes
- `name: str = "Abi"`
- `description: str`
- `logo_url: str`
- `system_prompt: str`  
  Orchestration prompt with constraints (no fabricated capabilities, preserve user language, etc.).
- `suggestions: list[dict]`  
  UI/UX suggestion(s) (e.g., “Abi Presentation”).

#### Methods
- `get_model() -> ChatModel` *(static)*  
  Returns the default chat model via `naas_abi.models.default.get_model()`.
- `get_tools(cls) -> list` *(static)*  
  Builds tool instances from the `naas_abi_core.modules.templatablesparqlquery` module, limited to:
  - `find_business_proposal_agents`
  - `find_coding_agents`
  - `find_math_agents`
  - `find_best_value_agents`
  - `find_fastest_agents`
  - `find_cheapest_agents`
- `get_agents(cls) -> tuple[list, AgentSharedState]` *(static)*  
  Discovers agent classes from all loaded modules in `ABIModule.get_instance().engine.modules`, instantiates/duplicates them, and returns:
  - `agents`: list of sub-agent instances
  - `agent_shared_state`: `AgentSharedState(thread_id="0", supervisor_agent="Abi")`  
  Also avoids adding itself as a sub-agent (prevents recursion).
- `get_intents(agents: list) -> list` *(static)*  
  Builds `Intent` entries for:
  - “Chat with {agent.name} Agent” (DIRECT scope)
  - Each agent’s own `intents` (if present), excluding those with `IntentScope.DIRECT`
- `New(agent_shared_state: Optional[AgentSharedState]=None, agent_configuration: Optional[AgentConfiguration]=None) -> AbiAgent` *(class method)*  
  Factory that:
  - collects tools, agents, intents
  - constructs an `AgentConfiguration` if none provided (injects tool/agent summaries into `system_prompt` via `replace("[TOOLS]", ...)` and `replace("[AGENTS]", ...)`)
  - returns a fully constructed `AbiAgent`

## Configuration/Dependencies
- Depends on a configured `naas_abi.ABIModule` singleton with an `engine.modules` registry.
- Requires the module key: `"naas_abi_core.modules.templatablesparqlquery"` to be present in `engine.modules`, and to be an instance of `naas_abi_core.modules.templatablesparqlquery.ABIModule` (asserted).
- Uses `naas_abi_core.logger` for debug logging in `New()`.
- Run hint (from docstring): `LOG_LEVEL=DEBUG uv run abi chat abi AbiAgent`

## Usage
Minimal creation of the agent instance:

```python
from naas_abi.agents.AbiAgent import AbiAgent

abi = AbiAgent.New()
print(abi.name)
```

## Caveats
- Tool availability depends on the `templatablesparqlquery` module being loaded under the exact module key in `ABIModule.get_instance().engine.modules` (an assertion will fail otherwise).
- Sub-agents are discovered dynamically from loaded modules; if no modules expose agents, `agents` (and derived intents) may be empty.
- `agent_shared_state` passed to `New()` is ignored/overwritten by `get_agents()` in the current implementation.

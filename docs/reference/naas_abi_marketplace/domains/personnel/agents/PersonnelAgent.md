# PersonnelAgent

## What it is
`PersonnelAgent` is an `Agent` specialized for Human Resources workflows (recruitment, employee relations, policy development, performance management, training, compliance). It:
- Uses the workspace default chat model from the default model registry.
- Loads a fixed set of personnel-related tools from the templatable SPARQL query module.
- Provides optional message hooks (`onHumanMessage`, `onAImessage`) for observation/logging.

## Public API

### Class: `PersonnelAgent(Agent)`
HR-focused agent with predefined metadata and prompt.

- Class attributes:
  - `name: str` — `"Personnel"`
  - `description: str` — HR expert description
  - `logo_url: str` — asset path
  - `system_prompt: str` — prompt template containing a `[TOOLS]` placeholder
  - `suggestions: list[dict]` — UI suggestion templates (job description, interview questions, HR policy, performance review)

#### `@classmethod get_tools() -> list`
Loads tools by name from the personnel domain engine’s templatable SPARQL query module.

- Tool labels loaded:
  - `find_active_employees`
  - `find_employee_by_id`
  - `find_employees_by_status`
  - `find_employees_by_organization`
  - `find_open_job_positions`
  - `find_positions_by_title`
  - `find_headcount_by_job_family`
  - `find_birth_registrations`

#### `@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> PersonnelAgent`
Factory constructor that:
- Fetches the default chat model via `get_default_model_registry()`.
- Loads tools via `get_tools()`.
- Builds an `AgentConfiguration` (if not provided) by injecting a generated tools section into `system_prompt` (replacing `[TOOLS]`).
- Creates a default `AgentSharedState(thread_id="0")` if not provided.
- Returns an initialized `PersonnelAgent`.

#### `onHumanMessage(message: AnyMessage) -> None`
Hook invoked once per turn, before the user message reaches the model. Default implementation is empty (commented example only).

#### `onAImessage(message: AnyMessage, agent_name: str) -> None`
Hook invoked when an AI message is emitted by this agent or its sub-agents (tool-call-only messages are not reported). Default implementation is empty (commented example only).

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry` (must be initialized)
  - `naas_abi_core.modules.templatablesparqlquery.ABIModule` for tool loading
- Depends on `naas_abi_marketplace.domains.personnel.ABIModule`:
  - Must expose an engine module keyed by `"naas_abi_core.modules.templatablesparqlquery"`
- Uses `langchain_core.messages.AnyMessage` for hook signatures.

## Usage
```python
from naas_abi_marketplace.domains.personnel.agents.PersonnelAgent import PersonnelAgent

agent = PersonnelAgent.New()

# Inspect loaded tools
print([t.name for t in agent.tools])
```

## Caveats
- `New()` asserts the default model registry is initialized (`"ModelRegistryService not initialized"` if not).
- `get_tools()` asserts the templatable SPARQL query module is of the expected type; personnel domain module wiring must be correct.
- Message hooks run inline on the streaming thread; keep them fast (slow work should be offloaded).

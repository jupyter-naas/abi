# KnowledgeGraphBuilderAgent

## What it is
A factory and agent definition for a **Knowledge Graph Builder** assistant. It constructs an `Agent` pre-configured with a system prompt and a set of tools/pipelines to search ontology classes/individuals and to add/update/merge/remove individuals in a triplestore.

## Public API

### Constants
- `NAME: str` — Display name: `"Knowledge Graph Builder"`.
- `AVATAR_URL: str` — RDF logo URL.
- `DESCRIPTION: str` — High-level purpose description.
- `SYSTEM_PROMPT: str` — Operational instructions for the agent (confirmation requirements, tool usage guidelines, constraints).
- `SUGGESTIONS: list` — Suggested user actions/prompts for UI/help.

### Functions
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[Agent]`
  - Builds and returns a `KnowledgeGraphBuilderAgent` instance.
  - Wires a chat model, system prompt (if none provided), shared state (if none provided), and a collection of tools from various workflows/pipelines plus templated SPARQL query tools.

### Classes
- `class KnowledgeGraphBuilderAgent(Agent)`
  - Concrete agent type; no additional behavior beyond base `Agent`.

## Configuration/Dependencies

### Runtime dependencies (imported and used)
- `naas_abi.models.default.get_model()` — provides the chat model.
- `naas_abi.ABIModule.get_instance()` — provides access to `MODULE.engine.services.triple_store`.
- Workflows/Pipelines used to produce tools:
  - `SearchIndividualWorkflow` (+ `SearchIndividualWorkflowConfiguration`)
  - `AddIndividualPipeline` (+ `AddIndividualPipelineConfiguration`) — depends on the search workflow configuration
  - `InsertDataSPARQLPipeline` (+ `InsertDataSPARQLPipelineConfiguration`)
  - `GetSubjectGraphWorkflow` (+ `GetSubjectGraphWorkflowConfiguration`)
  - `UpdateDataPropertyPipeline` (+ `UpdateDataPropertyPipelineConfiguration`)
  - `MergeIndividualsPipeline` (+ `MergeIndividualsPipelineConfiguration`)
  - `RemoveIndividualPipeline` (+ `RemoveIndividualPipelineConfiguration`)
- Templated SPARQL query tools:
  - `naas_abi_core.modules.templatablesparqlquery.ABIModule.get_instance().get_tools([...])`

### Agent configuration defaults
- If `agent_configuration` is not provided, it uses:
  - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
- If `agent_shared_state` is not provided, it uses:
  - `AgentSharedState()`

## Usage

```python
from naas_abi.agents.KnowledgeGraphBuilderAgent import create_agent

agent = create_agent()

# The returned object is an Agent configured with tools for KG operations.
# How you run/chat with the agent depends on the naas_abi_core Agent runtime.
print(agent.name)
```

## Caveats
- `create_agent()` requires a working `ABIModule` singleton and an initialized `MODULE.engine.services.triple_store`; missing/invalid module setup will prevent tool configuration.
- The class `KnowledgeGraphBuilderAgent` itself adds no behavior; functionality comes from the base `Agent` and the attached tools.
- Although the system prompt instructs the agent to ask for confirmation before ADD/UPDATE/MERGE/REMOVE, enforcement depends on the agent runtime and tool-calling behavior (this file only defines the prompt).

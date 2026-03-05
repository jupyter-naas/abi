# KnowledgeGraphBuilderAgent

## What it is
A factory-backed agent definition for building and maintaining a knowledge graph (triplestore) via a set of ontology/triplestore tools and pipelines. The module mainly provides:
- Agent metadata (name, avatar, description).
- A detailed `SYSTEM_PROMPT` governing safe operations (ask confirmation before add/update/merge/remove).
- `create_agent()` to assemble an `Agent` with the appropriate model, tools, state, and configuration.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[Agent]`
  - Builds and returns a configured `KnowledgeGraphBuilderAgent`.
  - Assembles a chat model and a toolset that supports searching, reading, adding, updating, merging, and removing individuals in a triplestore.
- `class KnowledgeGraphBuilderAgent(Agent)`
  - Concrete agent class (no additional behavior beyond `Agent` in this file).

## Configuration/Dependencies
- **Core types**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`.
- **Model**
  - `naas_abi.models.default.get_model()` supplies the chat model used by the agent.
- **Module singleton**
  - `naas_abi.ABIModule.get_instance()` provides access to `MODULE.engine.services.triple_store`.
- **Tooling assembled in `create_agent()`**
  - Workflows/Pipelines (converted to tools via `.as_tools()`):
    - `SearchIndividualWorkflow` (initialized first; its config is passed to the add pipeline)
    - `AddIndividualPipeline`
    - `InsertDataSPARQLPipeline`
    - `GetSubjectGraphWorkflow`
    - `UpdateDataPropertyPipeline`
    - `MergeIndividualsPipeline`
    - `RemoveIndividualPipeline`
    - Specialized update pipelines:
      - `UpdatePersonPipeline`, `UpdateSkillPipeline`, `UpdateCommercialOrganizationPipeline`,
        `UpdateLinkedInPagePipeline`, `UpdateWebsitePipeline`, `UpdateLegalNamePipeline`,
        `UpdateTickerPipeline`
  - Ontology/SPARQL query tools from:
    - `naas_abi_core.modules.templatablesparqlquery.ABIModule.get_instance().get_tools(...)`
    - Tool names requested: `search_class`, `count_instances_by_class`, `get_individuals_from_class`,
      `search_individuals_from_class`, `add_individual`, `update_data_property`,
      `merge_individuals`, `remove_individuals`
- **Default configuration**
  - If no `agent_configuration` is provided: `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
  - If no `agent_shared_state` is provided: `AgentSharedState()`

## Usage
```python
from naas_abi.agents.KnowledgeGraphBuilderAgent import create_agent

agent = create_agent()
# agent is an instance of KnowledgeGraphBuilderAgent with tools attached
```

## Caveats
- The agent’s `SYSTEM_PROMPT` explicitly requires **user confirmation before** performing operations that mutate the triplestore: **ADD**, **INSERT DATA**, **UPDATE**, **MERGE**, **REMOVE**.
- Tool availability depends on `ABIModule` being initialized and providing `MODULE.engine.services.triple_store`.

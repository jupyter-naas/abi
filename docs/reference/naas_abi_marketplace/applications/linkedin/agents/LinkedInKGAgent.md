# LinkedInKGAgent

## What it is
`LinkedInKGAgent` is an `IntentAgent` specialization for querying LinkedIn data stored in a knowledge graph. It:
- Loads a fixed set of SPARQL query tools from the templatable SPARQL query module.
- Adds two vector-similarity lookup tools to resolve person/company URIs.
- Builds an agent configuration whose system prompt includes the generated tool list.

## Public API

### Class: `LinkedInKGAgent(IntentAgent)`
Class attributes (agent metadata and prompt):
- `name`: `"LinkedIn_KG"`
- `description`: `"Helps users query and understand LinkedIn data stored in a knowledge graph."`
- `avatar_url`: LinkedIn logo URL
- `suggestions`: `[]`
- `system_prompt`: Prompt template containing a `[TOOLS]` placeholder that is replaced at runtime.

#### `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> LinkedInKGAgent`
Creates and returns a configured `LinkedInKGAgent` instance.

What it wires:
- **Chat model / embeddings**
  - Uses `ABIModule.get_instance().engine.services.model_registry` to get:
    - `registry.get_default_chat_model()`
    - `registry.get_default_embedding_model().model` (used for vector search)
- **SPARQL tools**
  - Fetches tools via `TemplatableSparqlQueryABIModule.get_instance().get_tools(...)` for:
    - `linkedin_count_connections_by_person`
    - `linkedin_search_connections_by_person`
    - `linkedin_search_connections_by_organization`
    - `linkedin_search_connections_by_job_position`
    - `linkedin_search_person_info`
- **Vector-search tools** (added as `langchain_core.tools.StructuredTool`)
  - `linkedin_search_person_uri` (collection: `linkedin_persons`, param: `person_name`)
  - `linkedin_search_company_uri` (collection: `linkedin_companies`, param: `company_name`)
  - Each tool returns a `list[dict]` with items like: `{"uri": ..., "label": ..., "score": ...}` or an `{"error": ...}` dict on failure.
- **Intents** (`IntentType.TOOL`)
  - `"Who is connected with {person}?"` → `linkedin_search_connections_by_person_name`
  - `"How many connections does {person} have?"` → `linkedin_count_connections_by_person`
  - `"What do you know about {person}?"` → `linkedin_get_connection_information`
  - `"What is {person}'s email address?"` → `linkedin_search_email_address_by_person_uri`

Defaulting behavior:
- If `agent_configuration` is not provided, it creates one with the tool-injected `system_prompt`.
- If `agent_shared_state` is not provided, it creates `AgentSharedState(thread_id="0")`.

## Configuration/Dependencies
Runtime dependencies assumed by `New()`:
- `naas_abi_marketplace.applications.linkedin.ABIModule.get_instance()` with an initialized `engine` containing:
  - `engine.services.model_registry` (must not be `None`; asserted)
  - `engine.services.vector_store` (used for similarity search)
  - `engine.modules["naas_abi_core.modules.templatablesparqlquery"]` (must be a `TemplatableSparqlQueryABIModule`; asserted)
- Python packages used internally:
  - `numpy`
  - `pydantic`
  - `langchain_core.tools.StructuredTool`

Vector store collections referenced:
- `linkedin_persons`
- `linkedin_companies`

## Usage
```python
from naas_abi_core.services.agent.IntentAgent import AgentSharedState
from naas_abi_marketplace.applications.linkedin.agents.LinkedInKGAgent import LinkedInKGAgent

agent = LinkedInKGAgent.New(agent_shared_state=AgentSharedState(thread_id="demo"))
print(agent.name)  # LinkedIn_KG
```

## Caveats
- `New()` asserts the presence of `model_registry` and a correctly-typed templatable SPARQL query module; missing/incorrect runtime initialization will fail fast.
- Several intent targets are not among the SPARQL tools explicitly loaded in this file (e.g., `linkedin_search_connections_by_person_name`, `linkedin_get_connection_information`, `linkedin_search_email_address_by_person_uri`). Successful execution depends on those tools being available elsewhere in the runtime/tooling.
- Vector-search tools require the referenced vector store collections to exist and contain metadata fields `uri` and `label` for meaningful results.

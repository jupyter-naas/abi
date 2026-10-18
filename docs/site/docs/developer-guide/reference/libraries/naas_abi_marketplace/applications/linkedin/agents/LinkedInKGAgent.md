# LinkedInKGAgent

## What it is
A factory and thin agent wrapper that builds an `IntentAgent` specialized for querying LinkedIn data stored in a knowledge graph. It:
- Loads SPARQL query tools from the “templatable SPARQL query” module.
- Adds vector-search tools to resolve person/company URIs via semantic similarity.
- Returns an `IntentAgent` instance (`LinkedInKGAgent`) configured with a LinkedIn-focused system prompt and intents.

## Public API

### Constants
- `NAME`: `"LinkedIn_KG"`
- `DESCRIPTION`: Human-readable agent description.
- `AVATAR_URL`: LinkedIn logo URL.
- `SYSTEM_PROMPT`: System instructions template. Tool list is injected at runtime.
- `SUGGESTIONS`: Empty list (`list[str]`).

### Functions
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Creates and returns a configured `LinkedInKGAgent`.
  - Wires SPARQL tools and two vector-search tools:
    - `linkedin_search_person_uri` (collection: `linkedin_persons`)
    - `linkedin_search_company_uri` (collection: `linkedin_companies`)

### Classes
- `class LinkedInKGAgent(IntentAgent)`
  - No additional behavior; inherits everything from `IntentAgent`.

## Configuration/Dependencies
This module relies on an existing Naas ABI runtime with modules/services available:

- **Naas ABI core**
  - `naas_abi_core.services.agent.IntentAgent` (`IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`)
  - `naas_abi_core.modules.templatablesparqlquery.ABIModule` to provide SPARQL tools via `get_tools(...)`
  - `naas_abi_core.services.vector_store.VectorStoreService` for similarity search

- **Marketplace / Application**
  - `naas_abi_marketplace.applications.linkedin.ABIModule.get_instance().engine` must be initialized and contain:
    - module key: `"naas_abi_core.modules.templatablesparqlquery"`
    - service: `engine.services.vector_store`

- **LLM / embeddings**
  - Chat model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
  - Embeddings: `langchain_openai.OpenAIEmbeddings(model="text-embedding-3-large")`
  - Requires `numpy`, `pydantic`, `langchain_core.tools.StructuredTool`

## Usage
```python
from naas_abi_marketplace.applications.linkedin.agents.LinkedInKGAgent import create_agent
from naas_abi_core.services.agent.IntentAgent import AgentSharedState

agent = create_agent(agent_shared_state=AgentSharedState(thread_id="demo"))

# How you invoke/run the agent depends on IntentAgent's interface in naas_abi_core.
# This module only constructs and returns the configured agent instance.
print(agent.name)
```

## Caveats
- The factory assumes the LinkedIn `ABIModule` engine is already initialized and contains the required module/service; otherwise tool wiring will fail (including an `assert` on the SPARQL module type).
- Two intents reference tool names not defined in the tool list built here (e.g., `linkedin_search_connections_by_person_name`, `linkedin_get_connection_information`, `linkedin_search_email_address_by_person_uri`). Successful execution depends on those tools existing in the broader runtime/tool registry.
- Vector search tools require populated vector store collections named:
  - `linkedin_persons`
  - `linkedin_companies`

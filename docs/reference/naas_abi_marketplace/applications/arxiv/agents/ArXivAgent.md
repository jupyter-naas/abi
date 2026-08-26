# ArXivAgent

## What it is
- A specialized `Agent` configured to search, retrieve metadata, ingest, and query ArXiv papers.
- Wires together ArXiv integration tools, a paper ingestion pipeline (triple store + PDF storage), and a query workflow over stored data.

## Public API
- `class ArXivAgent(Agent)`
  - Agent metadata:
    - `name = "ArXivAgent"`
    - `description = "Search and analyze research papers from ArXiv"`
    - `avatar_url = ".../ArXiv_web.svg.png"`
    - `system_prompt`: instructions describing tool usage (search first, fetch details, optionally ingest, then query knowledge graph).
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> ArXivAgent`
    - Creates a fully configured `ArXivAgent` instance with:
      - Default chat model from `ABIModule`’s `model_registry.get_default_chat_model()`
      - Tools from:
        - `ArXivIntegration.as_tools(ArXivIntegrationConfiguration())`
        - `ArXivPaperPipeline(...).as_tools()` using:
          - `triple_store` from `ABIModule.get_instance().engine.services.triple_store`
          - `storage_base_path="storage/triplestore/application-level/arxiv"`
          - `pdf_storage_path="datastore/application-level/arxiv"`
        - `ArXivQueryWorkflow(...).as_tools()` using:
          - `storage_path="storage/triplestore/application-level/arxiv"`
      - Defaults when not provided:
        - `AgentConfiguration(system_prompt=cls.system_prompt)`
        - `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Core agent framework:
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
- ArXiv application module/services:
  - `naas_abi_marketplace.applications.arxiv.ABIModule`
  - Requires `ABIModule.get_instance().engine.services.model_registry` (asserted non-`None`)
  - Uses `ABIModule.get_instance().engine.services.triple_store`
- Tool providers:
  - `ArXivIntegration`, `ArXivIntegrationConfiguration`
  - `ArXivPaperPipeline`, `ArXivPaperPipelineConfiguration`
  - `ArXivQueryWorkflow`, `ArXivQueryWorkflowConfiguration`

## Usage
```python
from naas_abi_marketplace.applications.arxiv.agents.ArXivAgent import ArXivAgent

agent = ArXivAgent.New()

# Use the base Agent interface to run prompts (exact method depends on Agent implementation).
# Example (pseudo):
# result = agent.run("Find recent papers on graph neural networks and summarize key themes.")
# print(result)
```

## Caveats
- Requires `ABIModule` to be initialized with:
  - a working `model_registry` (otherwise an assertion error is raised)
  - a `triple_store` service for the ingestion pipeline
- The file only configures the agent and tools; how to execute conversations depends on the underlying `Agent` API.

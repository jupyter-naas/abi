# ArXivAgent

## What it is
- A thin wrapper around the core `Agent` that configures an ArXiv-focused assistant.
- Bundles ArXiv search/metadata tools, a paper ingestion pipeline (knowledge graph + PDF download), and a query workflow for stored papers.

## Public API
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> Agent`
  - Creates and returns a configured `ArXivAgent` instance with:
    - Chat model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
    - Tools from:
      - `ArXivIntegration.as_tools(...)`
      - `ArXivPaperPipeline(...).as_tools()`
      - `ArXivQueryWorkflow(...).as_tools()`
    - Default `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if none provided
    - Default `AgentSharedState()` if none provided

- `class ArXivAgent(Agent)`
  - Specialized agent class for ArXiv usage (no additional behavior beyond `Agent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.Agent`:
  - `Agent`, `AgentConfiguration`, `AgentSharedState`
- Initializes the ArXiv application module:
  - `from naas_abi_marketplace.applications.arxiv import ABIModule`
  - Uses `module.engine.services.triple_store`
- Tooling components:
  - `ArXivIntegration` + `ArXivIntegrationConfiguration`
  - `ArXivPaperPipeline` + `ArXivPaperPipelineConfiguration`
    - `storage_base_path="storage/triplestore/application-level/arxiv"`
    - `pdf_storage_path="datastore/application-level/arxiv"`
  - `ArXivQueryWorkflow` + `ArXivQueryWorkflowConfiguration`
    - `storage_path="storage/triplestore/application-level/arxiv"`
- Built-in prompt:
  - `SYSTEM_PROMPT` describes expected tool usage (search first, then fetch details, optionally ingest to KG, then query KG).

## Usage
```python
from naas_abi_marketplace.applications.arxiv.agents.ArXivAgent import create_agent

agent = create_agent()

# Interact using the base Agent interface (method names depend on Agent implementation).
# Example (pseudo):
# response = agent.run("Find recent papers about retrieval-augmented generation and summarize trends.")
# print(response)
```

## Caveats
- Requires the ArXiv `ABIModule` engine and its `triple_store` service to be available at runtime.
- Tool availability and how to invoke the agent depend on the underlying `Agent` implementation (this file only wires configuration and tools).

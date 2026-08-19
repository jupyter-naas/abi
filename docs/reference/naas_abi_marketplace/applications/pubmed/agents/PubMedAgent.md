# PubMedAgent

## What it is
- An `Agent` specialized for searching PubMed, with:
  - Tools from `PubMedPipeline`.
  - An additional tool to download PubMed Central PDFs by PMCID and store them in object storage.
- Provides a built-in system prompt instructing results to be displayed as Markdown tables.

## Public API
- **Class `PubMedAgent(Agent)`**
  - **Class attributes**
    - `name: str = "PubMedAgent"`
    - `description: str = "PubMedAgent is an agent that can search for papers in PubMed."`
    - `system_prompt: str` (includes Markdown-table requirement)
  - **Class method `New(cls, agent_shared_state=None, agent_configuration=None) -> PubMedAgent`**
    - Factory that builds and returns a configured `PubMedAgent`.
    - Initializes:
      - Chat model from `ABIModule.get_instance().engine.services.model_registry.get_default_chat_model()`.
      - Tools from `PubMedPipeline(...).as_tools()` plus a `download_pdf` tool (defined inside `New`).
      - `AgentConfiguration(system_prompt=cls.system_prompt)` if not provided.
      - `AgentSharedState(thread_id=<uuid hex>)` if not provided.

- **Tool `download_pdf(pmcids: list[str]) -> str`** *(defined inside `PubMedAgent.New`)*  
  - LangChain tool (`@tool`) with description: `"Download a PDF from PubMed Central using it's PMCID"`.
  - For each PMCID:
    - Downloads PDF bytes via `PubMedIntegration(PubMedAPIConfiguration()).download_pubmed_central_pdf(pmcid)`.
    - Writes to a temporary file, uploads to object storage:
      - bucket/prefix: `"pubmed/pdfs"`
      - key: `"{pmcid}.pdf"`
    - Deletes the temporary file.
  - Executes downloads concurrently via `ThreadPoolExecutor(max_workers=10)`.
  - Returns `"PDFs downloaded and saved."`.

## Configuration/Dependencies
- **Runtime services (required)**
  - `ABIModule.get_instance().engine.services.model_registry` must be initialized (asserted).
  - `ABIModule.get_instance().engine.services.object_storage` must be available for PDF storage uploads.
- **PubMed integration**
  - Uses `PubMedIntegration` and `PubMedAPIConfiguration` to fetch PubMed Central PDFs.
- **Pipeline**
  - Uses `PubMedPipeline` and `PubMedPipelineConfiguration` to provide additional tools.

## Usage
```python
from naas_abi_marketplace.applications.pubmed.agents.PubMedAgent import PubMedAgent

agent = PubMedAgent.New()

# Agent tools include PubMedPipeline tools plus "download_pdf".
# How you call tools depends on the Agent runtime in naas_abi_core.
print(agent.name, agent.description)
```

## Caveats
- `download_pdf` is defined inside `PubMedAgent.New`; it is not importable from the module as a top-level function.
- `download_pdf` prints `Downloading {pmcid}` to stdout for each PMCID.
- No explicit error handling is implemented for download/upload failures; exceptions will propagate.
- The system prompt requests Markdown table output, but enforcement is prompt-based (not programmatic).

# PubMedAgent

## What it is
- A thin agent factory for a PubMed-focused `Agent` configured with:
  - A PubMed search pipeline exposed as tools.
  - A helper tool to download PubMed Central PDFs by PMCID and store them in object storage.
- Includes constants for the agent name, description, and system prompt.

## Public API
- **Class `PubMedAgent(Agent)`**
  - Subclasses `naas_abi_core.services.agent.Agent.Agent`.
  - No additional methods/attributes (defined as `pass`).

- **Tool function `download_pdf(pmcids: List[str]) -> str`**
  - LangChain tool (`@tool`) to download one or more PDFs from PubMed Central using PMCIDs.
  - Behavior:
    - For each PMCID:
      - Downloads PDF bytes via `PubMedIntegration(PubMedAPIConfiguration()).download_pubmed_central_pdf(pmcid)`.
      - Writes to a temporary file, then uploads to object storage at:
        - bucket/prefix: `"pubmed/pdfs"`
        - key: `"{pmcid}.pdf"`
      - Deletes the temporary file.
    - Runs downloads concurrently via `ThreadPoolExecutor(max_workers=10)`.
  - Returns: `"PDFs downloaded and saved."`

- **Factory function `create_agent() -> PubMedAgent`**
  - Builds a `PubMedPipeline` and converts it to tools via `pipeline.as_tools()`.
  - Returns a `PubMedAgent` configured with:
    - `name`, `description`, `system_prompt` constants.
    - Chat model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model.model` (cast to `ChatModel`).
    - Tools: pipeline tools + `download_pdf`.
    - State: `AgentSharedState(thread_id=<random uuid hex>)`.
    - `memory=None`, `agents=[]`.

## Configuration/Dependencies
- **External services**
  - Object storage is accessed through `ABIModule.get_instance().engine.services.object_storage` and must be available/configured in the runtime.

- **PubMed integration**
  - Uses `PubMedIntegration` + `PubMedAPIConfiguration` to download PDFs from PubMed Central.

- **Pipeline**
  - `PubMedPipeline(PubMedPipelineConfiguration())` is used to provide additional tools (not defined in this file).

- **Model**
  - Uses the `gpt_4_1` chat model wrapper imported as `model`.

## Usage
```python
from naas_abi_marketplace.applications.pubmed.agents.PubMedAgent import create_agent, download_pdf

agent = create_agent()

# Use the tool directly (requires ABIModule/object_storage to be configured in your environment)
result = download_pdf(["PMC1234567", "PMC7654321"])
print(result)
```

## Caveats
- `download_pdf` prints `"Downloading {pmcid}"` to stdout for each PMCID.
- Files are downloaded concurrently (up to 10 workers); failures/exceptions during download or storage upload are not handled in this function.
- The agent’s system prompt requires displaying tool results as a Markdown table, but this file does not enforce formatting beyond the prompt text.

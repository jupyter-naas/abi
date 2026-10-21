# ArXivPaperPipeline

## What it is
- A `Pipeline` that:
  - Fetches an arXiv paper by ID via `ArXivIntegration`.
  - Builds an RDF graph (`ABIGraph`) describing the paper, publication time, authors, and categories using ABI/BFO terms.
  - Writes the graph to a unique Turtle (`.ttl`) file.
  - Optionally downloads the paper PDF and records the local PDF path in the graph (and rewrites the `.ttl`).

## Public API
- `ArXivPaperPipelineConfiguration` (dataclass, extends `PipelineConfiguration`)
  - `arxiv_integration_config: ArXivIntegrationConfiguration` — configuration for arXiv integration.
  - `triple_store: ITripleStoreService` — required field but not used in this pipeline implementation.
  - `storage_base_path: str = "storage/triplestore/application-level/arxiv"` — directory for `.ttl` output.
  - `pdf_storage_path: str = "datastore/application-level/arxiv"` — directory for downloaded PDFs.

- `ArXivPaperPipelineParameters` (extends `PipelineParameters`)
  - `paper_id: str` — arXiv paper ID.
  - `download_pdf: bool = True` — whether to download the PDF (if a `pdf_url` is available).

- `ArXivPaperPipeline` (extends `Pipeline`)
  - `__init__(configuration: ArXivPaperPipelineConfiguration)`
    - Instantiates `ArXivIntegration`.
    - Ensures `storage_base_path` and `pdf_storage_path` directories exist.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Requires `parameters` to be `ArXivPaperPipelineParameters` (raises `TypeError` otherwise).
    - Creates an `ABIGraph` and adds:
      - Paper individual (`ABI.ArXivPaper`) with label, description, and URL.
      - Published time as a temporal instant (`BFO.BFO_0000203`) linked via `BFO.BFO_0000222`.
      - Authors (`ABI.ArXivAuthor`) linked via `ABI.hasAuthor`.
      - Categories (`ABI.ArXivCategory`) linked via `ABI.hasCategory`.
    - Serializes graph to a unique `.ttl` file named from a sanitized title + UUID.
    - If `download_pdf` and `pdf_url` are present:
      - Adds `(paper, ABI.localFilePath, Literal(pdf_filepath))` to the graph.
      - Downloads the PDF via `requests.get(..., stream=True)` into `pdf_storage_path`.
      - Rewrites the `.ttl` to include the local file path.
    - Prints paths and download errors to stdout.
  - `as_tools() -> list[BaseTool]`
    - Returns a LangChain `StructuredTool` named `"arxiv_paper_pipeline"` that calls `run()` using `ArXivPaperPipelineParameters`.
  - `as_api(...) -> None`
    - Stub: accepts parameters but does not register any routes or implement behavior.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.arxiv.integrations.ArXivIntegration` (`get_paper`)
  - `naas_abi_core.utils.Graph`: `ABIGraph`, `ABI`, `BFO`
  - `rdflib`: `Graph`, `Literal`
  - `requests` for PDF download
  - `langchain_core.tools` for `StructuredTool`
  - `fastapi.APIRouter` (API method is present but unused)
- Filesystem:
  - Creates directories:
    - `storage_base_path` for `.ttl`
    - `pdf_storage_path` for `.pdf`

## Usage
```python
from naas_abi_marketplace.applications.arxiv.pipelines.ArXivPaperPipeline import (
    ArXivPaperPipeline,
    ArXivPaperPipelineConfiguration,
    ArXivPaperPipelineParameters,
)
from naas_abi_marketplace.applications.arxiv.integrations.ArXivIntegration import (
    ArXivIntegrationConfiguration,
)

arxiv_cfg = ArXivIntegrationConfiguration(...)  # provide required fields
triple_store = ...  # ITripleStoreService (required by config, not used here)

pipeline = ArXivPaperPipeline(
    ArXivPaperPipelineConfiguration(
        arxiv_integration_config=arxiv_cfg,
        triple_store=triple_store,
    )
)

graph = pipeline.run(ArXivPaperPipelineParameters(paper_id="1706.03762", download_pdf=True))
print(len(graph))
```

## Caveats
- Side effects:
  - Always writes a `.ttl` file to disk.
  - Optionally downloads and writes a `.pdf` file to disk.
  - Uses `print()` for status/errors.
- `triple_store` is required in configuration but not used in `run()`.
- PDF download failures are caught and printed; the pipeline still returns the graph.
- `as_api()` is incomplete and does not expose endpoints.

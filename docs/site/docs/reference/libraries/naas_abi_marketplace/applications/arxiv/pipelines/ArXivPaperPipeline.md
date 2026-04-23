# ArXivPaperPipeline

## What it is
- A `Pipeline` that fetches an ArXiv paper by ID, builds an RDF graph (ABI/BFO ontology terms), writes the graph to a Turtle (`.ttl`) file, and optionally downloads the paper PDF and records its local path in the graph.

## Public API
- `ArXivPaperPipelineConfiguration` (dataclass)
  - Holds runtime configuration:
    - `arxiv_integration_config: ArXivIntegrationConfiguration`
    - `triple_store: ITripleStoreService` (present in config but not used in this file)
    - `storage_base_path: str` (default: `"storage/triplestore/application-level/arxiv"`)
    - `pdf_storage_path: str` (default: `"datastore/application-level/arxiv"`)

- `ArXivPaperPipelineParameters` (pydantic model)
  - `paper_id: str` — ArXiv paper ID
  - `download_pdf: bool = True` — whether to download the PDF

- `ArXivPaperPipeline(configuration)`
  - `run(parameters) -> rdflib.Graph`
    - Validates parameter type (`ArXivPaperPipelineParameters`)
    - Fetches paper metadata via `ArXivIntegration.get_paper(paper_id)`
    - Adds to an `ABIGraph`:
      - Paper individual (type `ABI.ArXivPaper`, with label/description/url)
      - Published timestamp as a `BFO.BFO_0000203` “temporal instant”, linked via `BFO.BFO_0000222`
      - Authors as `ABI.ArXivAuthor`, linked via `ABI.hasAuthor`
      - Categories as `ABI.ArXivCategory`, linked via `ABI.hasCategory`
    - Serializes graph to a uniquely named `.ttl` file under `storage_base_path`
    - If `download_pdf` is true and `pdf_url` exists:
      - Downloads PDF to `pdf_storage_path`
      - Adds `(paper, ABI.localFilePath, <local pdf path literal>)` to the graph
      - Rewrites the `.ttl` to include the local file path
  - `as_tools() -> list[BaseTool]`
    - Returns a single LangChain `StructuredTool` named `"arxiv_paper_pipeline"` that calls `run()` with `ArXivPaperPipelineParameters`.
  - `as_api(...) -> None`
    - Present but currently does nothing (returns `None` without registering routes).

## Configuration/Dependencies
- External services/libraries:
  - `ArXivIntegration` / `ArXivIntegrationConfiguration` (paper lookup)
  - `requests` (PDF download)
  - `rdflib` (`Graph`, `Literal`) and `naas_abi_core.utils.Graph` (`ABIGraph`, `ABI`, `BFO`)
  - `langchain_core.tools.StructuredTool` (tool wrapper)
  - `fastapi.APIRouter` (API hook is stubbed)
- Filesystem:
  - Ensures directories exist:
    - `storage_base_path` for Turtle files
    - `pdf_storage_path` for downloaded PDFs

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

# Provide real integration configuration and a triple store service instance as required by your environment.
arxiv_cfg = ArXivIntegrationConfiguration(...)  # depends on integration implementation
triple_store = ...  # must implement ITripleStoreService (not used by this pipeline)

cfg = ArXivPaperPipelineConfiguration(
    arxiv_integration_config=arxiv_cfg,
    triple_store=triple_store,
)

pipeline = ArXivPaperPipeline(cfg)

g = pipeline.run(
    ArXivPaperPipelineParameters(
        paper_id="1706.03762",
        download_pdf=True,
    )
)

print(len(g))  # number of RDF triples
```

## Caveats
- `as_api()` is a stub and does not expose any FastAPI routes.
- `triple_store` is required in configuration but is not used by `run()` in this implementation.
- Side effects:
  - Writes `.ttl` files and optionally `.pdf` files to disk.
  - Uses `print()` for status/errors; PDF download errors are caught and only printed (pipeline still returns the graph).

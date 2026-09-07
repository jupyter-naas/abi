# PubMedPipeline

## What it is
- A pipeline that searches PubMed within a date range and returns results as an RDF `Graph`.
- Optionally filters results to only include papers that have a non-`None` `downloadUrl` (downloadable from PubMed Central).

## Public API

### Classes

- `PubMedPipelineConfiguration(PipelineConfiguration)`
  - Pipeline configuration container (no additional fields).

- `PubMedPipelineParameters(PipelineParameters)`
  - Input parameters for running the pipeline.
  - Fields:
    - `query: str` — PubMed search query.
    - `start_date: str` — start date for the search.
    - `end_date: str | None = None` — end date for the search (if `None`, integration searches up to present).
    - `sort: Literal["pub_date", "Author", "JournalName", "relevance"] | None = "pub_date"` — sort order.
    - `downloadable_only: bool | None = False` — when `True`, only include results with `downloadUrl`.
    - `max_results: int | None = 100` — maximum number of results (validated `1..10000`).

- `PubMedPipeline(Pipeline)`
  - Main pipeline implementation.
  - Methods:
    - `__init__(configuration: PubMedPipelineConfiguration)`
      - Initializes the pipeline and an internal `PubMedIntegration(PubMedAPIConfiguration())`.
    - `run(parameters: PipelineParameters) -> Graph`
      - Executes the PubMed search via `PubMedIntegration.search_date_range(...)`.
      - Aggregates `result.rdf()` for each `PubMedPaperSummary` into a `Graph`.
      - Applies `downloadable_only` filtering based on `result.downloadUrl`.
      - Raises `TypeError` if `parameters` is not a `PubMedPipelineParameters`.
    - `as_api(...) -> None`
      - Declared but not implemented (`pass`).
    - `as_tools() -> list[BaseTool]`
      - Returns a LangChain `StructuredTool` named `search_downloadable_pubmed_papers` that returns Turtle serialization of the RDF graph.

## Configuration/Dependencies
- Core:
  - `naas_abi_core.pipeline`: `Pipeline`, `PipelineConfiguration`, `PipelineParameters`, `Graph`
  - `naas_abi_core.logger`
- PubMed integration:
  - `naas_abi_marketplace.applications.pubmed.integrations.PubMedAPI`:
    - `PubMedIntegration`, `PubMedAPIConfiguration`, `PubMedPaperSummary`
- Tooling / API hooks:
  - `langchain_core.tools`: `BaseTool`, `StructuredTool`
  - `fastapi`: `APIRouter` (referenced by `as_api`, not implemented)
- Script mode (`__main__`):
  - `click`, `rich`

## Usage

### Run from Python
```python
from naas_abi_marketplace.applications.pubmed.pipelines.PubMedPipeline import (
    PubMedPipeline,
    PubMedPipelineConfiguration,
    PubMedPipelineParameters,
)

pipeline = PubMedPipeline(PubMedPipelineConfiguration())
graph = pipeline.run(
    PubMedPipelineParameters(
        query="cancer biomarkers",
        start_date="2024-01-01",
        end_date="2024-03-01",
        downloadable_only=True,
        max_results=50,
    )
)

print(graph.serialize(format="turtle")[:500])
```

### Use as a LangChain tool
```python
from naas_abi_marketplace.applications.pubmed.pipelines.PubMedPipeline import (
    PubMedPipeline, PubMedPipelineConfiguration
)

tool = PubMedPipeline(PubMedPipelineConfiguration()).as_tools()[0]
ttl = tool.run({"query": "diabetes", "start_date": "2024-01-01", "end_date": None})
print(ttl[:300])
```

### Run as a script (writes `pubmed_output.ttl`)
```bash
python PubMedPipeline.py --query "diabetes" --start-date 2024-01-01 --end-date 2024-02-01
```

## Caveats
- `run()` requires `PubMedPipelineParameters`; passing any other `PipelineParameters` subtype raises `TypeError`.
- `as_api()` is not implemented.
- `downloadable_only=True` only includes results where `result.downloadUrl is not None`.

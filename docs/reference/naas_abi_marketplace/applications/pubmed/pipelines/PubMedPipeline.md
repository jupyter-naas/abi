# PubMedPipeline

## What it is
- A pipeline that queries PubMed within a date range and returns results as an RDF `Graph`.
- Can filter results to include only papers that have a `downloadUrl` (PubMed Central downloadable).

## Public API

### Classes

- `PubMedPipelineConfiguration(PipelineConfiguration)`
  - Pipeline configuration type (currently no additional fields).

- `PubMedPipelineParameters(PipelineParameters)`
  - Input parameters for running the pipeline.
  - Fields:
    - `query: str` — PubMed search query.
    - `start_date: str` — start date (string format expected by integration; CLI suggests `YYYY-MM-DD` or `YYYY/MM/DD`).
    - `end_date: Optional[str] = None` — end date; if `None`, searches up to present.
    - `sort: Optional[Literal["pub_date","Author","JournalName","relevance"]] = "pub_date"` — sorting mode.
    - `downloadable_only: Optional[bool] = False` — include only results with `downloadUrl`.
    - `max_results: Optional[int] = 100` — max results (1..10,000).

- `PubMedPipeline(Pipeline)`
  - Main pipeline class.
  - Methods:
    - `__init__(configuration: PubMedPipelineConfiguration)`
      - Initializes the pipeline and an internal `PubMedIntegration(PubMedAPIConfiguration())`.
    - `run(parameters: PipelineParameters) -> Graph`
      - Executes the PubMed query and returns an RDF `Graph` aggregated from result `rdf()` outputs.
      - Raises `ValueError` if `parameters` is not `PubMedPipelineParameters`.
    - `as_api(...) -> None`
      - Declared but not implemented (`pass`).
    - `as_tools() -> List[BaseTool]`
      - Returns a LangChain `StructuredTool` named `search_downloadable_pubmed_papers` that runs the pipeline and returns Turtle serialization.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.pipeline`: `Pipeline`, `PipelineConfiguration`, `PipelineParameters`, `Graph`
  - `naas_abi_marketplace.applications.pubmed.integrations.PubMedAPI`:
    - `PubMedIntegration`, `PubMedAPIConfiguration`, `PubMedPaperSummary`
  - LangChain: `langchain_core.tools.StructuredTool`
  - FastAPI: `fastapi.APIRouter` (only referenced by `as_api`, which is not implemented)
  - CLI dependencies when run as a script: `click`, `rich`

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

ttl = graph.serialize(format="turtle")
print(ttl[:500])
```

### Use as a LangChain tool
```python
pipeline = PubMedPipeline(PubMedPipelineConfiguration())
tool = pipeline.as_tools()[0]

turtle = tool.run({
    "query": "machine learning radiology",
    "start_date": "2024-01-01",
    "end_date": None,
    "downloadable_only": False,
    "max_results": 10,
})
print(turtle[:300])
```

### Run as a script (writes `pubmed_output.ttl`)
```bash
python PubMedPipeline.py --query "diabetes" --start-date 2024-01-01 --end-date 2024-02-01
```

## Caveats
- `PubMedPipeline.run()` only accepts `PubMedPipelineParameters`; passing any other `PipelineParameters` subtype raises `ValueError`.
- `as_api()` is not implemented.
- `downloadable_only=True` filters results by checking `result.downloadUrl is not None` before adding `result.rdf()` to the output graph.

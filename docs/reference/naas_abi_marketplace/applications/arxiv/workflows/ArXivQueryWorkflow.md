# ArXivQueryWorkflow

## What it is
A workflow for querying locally stored ArXiv RDF/Turtle (`.ttl`) files via RDFLib/SPARQL. It loads all `.ttl` files from a configured directory into a single in-memory graph and provides methods to:
- find authors for papers (by paper ID and/or title substring)
- find papers (by author substring and/or category substring)
- run arbitrary SPARQL queries
- read and return a fixed ontology schema file
- expose the above as LangChain tools and FastAPI routes

## Public API

### Configuration
- `@dataclass ArXivQueryWorkflowConfiguration(WorkflowConfiguration)`
  - `storage_path: str = "storage/triplestore/application-level/arxiv"`
  - Purpose: directory containing `*.ttl` files to load into the combined graph.

### Parameter models (Pydantic)
- `AuthorQueryParameters`
  - Fields: `paper_id: str | None`, `paper_title: str | None`
  - Purpose: inputs for author lookup.
- `PaperQueryParameters`
  - Fields: `author_name: str | None`, `category: str | None`
  - Purpose: inputs for paper lookup.
- `SchemaParameters`
  - No fields
  - Purpose: placeholder parameters for schema retrieval.
- `SparqlQueryParameters`
  - Fields: `query: str`
  - Purpose: SPARQL query input for custom query execution.

### Workflow
- `class ArXivQueryWorkflow(Workflow)`
  - `__init__(configuration: ArXivQueryWorkflowConfiguration)`
    - Purpose: store configuration (notably `storage_path`).
  - `query_authors(parameters: AuthorQueryParameters) -> dict[str, Any]`
    - Purpose: return authors for matching papers.
    - Output: `{"papers": [{"id": str, "title": str, "authors": [str, ...]}, ...]}` or `{"error": ...}` if no criteria.
  - `query_papers(parameters: PaperQueryParameters) -> dict[str, Any]`
    - Purpose: return matching papers by author/category.
    - Output: `{"papers": [{"id": str, "title": str, "pdf_url": str | None}, ...]}` or `{"error": ...}` if no criteria.
  - `get_schema(parameters: SchemaParameters) -> dict[str, str]`
    - Purpose: return ontology Turtle content from a fixed path.
    - Output: `{"schema": "<ttl text>"}` or `{"error": ...}` if missing.
  - `execute_query(parameters: SparqlQueryParameters) -> dict[str, Any]`
    - Purpose: run arbitrary SPARQL against the loaded graph.
    - Output: `{"results": [ {var: value, ...}, ... ]}` or `{"error": ...}` on failure.
  - `get_frequent_authors() -> dict[str, Any]`
    - Purpose: compute author frequency over stored papers.
    - Output: `{"authors": [{"name": str, "paper_count": int}, ...]}` or `{"error": ...}` on failure.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Purpose: expose as LangChain `StructuredTool`s:
      - `query_arxiv_authors`
      - `query_arxiv_papers`
      - `get_arxiv_schema`
      - `execute_arxiv_query`
      - `get_frequent_authors`
  - `as_api(router: fastapi.APIRouter, ...) -> None`
    - Purpose: register FastAPI endpoints:
      - `POST /arxiv/query-authors`
      - `POST /arxiv/query-papers`
      - `POST /arxiv/schema`
      - `POST /arxiv/query`

## Configuration/Dependencies
- Storage
  - Loads all `*.ttl` files from `ArXivQueryWorkflowConfiguration.storage_path`.
- Ontology file
  - `get_schema()` reads from: `src/custom/modules/arxiv_agent/ontologies/ArXivOntology.ttl` (path is hard-coded).
- Key imports/dependencies
  - `rdflib.Graph` and SPARQL querying
  - `naas_abi_core.utils.Graph.ABIGraph` (used as the combined graph container)
  - `fastapi.APIRouter` (for `as_api`)
  - `langchain_core.tools.StructuredTool` (for `as_tools`)
  - `pydantic.BaseModel` (parameter schemas)

## Usage

### Query from Python
```python
from naas_abi_marketplace.applications.arxiv.workflows.ArXivQueryWorkflow import (
    ArXivQueryWorkflow,
    ArXivQueryWorkflowConfiguration,
    AuthorQueryParameters,
    PaperQueryParameters,
    SparqlQueryParameters,
)

wf = ArXivQueryWorkflow(
    ArXivQueryWorkflowConfiguration(storage_path="storage/triplestore/application-level/arxiv")
)

print(wf.query_authors(AuthorQueryParameters(paper_id="2206.11097")))
print(wf.query_papers(PaperQueryParameters(author_name="smith")))

print(wf.execute_query(SparqlQueryParameters(query="""
PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5
""")))
```

### Expose via FastAPI
```python
from fastapi import FastAPI, APIRouter
from naas_abi_marketplace.applications.arxiv.workflows.ArXivQueryWorkflow import (
    ArXivQueryWorkflow, ArXivQueryWorkflowConfiguration
)

app = FastAPI()
router = APIRouter()

wf = ArXivQueryWorkflow(ArXivQueryWorkflowConfiguration())
wf.as_api(router)

app.include_router(router)
```

## Caveats
- Graph loading is per-call:
  - Each query method calls `_load_graph()` and re-reads all `.ttl` files each time.
- Missing/empty storage:
  - If `storage_path` does not exist or contains no `.ttl` files, the workflow prints a warning and returns empty result sets (or an `"error"` only when required parameters are missing).
- SPARQL string interpolation:
  - `query_authors()` and `query_papers()` embed user-provided strings directly into SPARQL via f-strings; malformed input can break queries.
- API coverage:
  - `get_frequent_authors()` is available via direct method call and `as_tools()`, but is not exposed as a FastAPI route in `as_api()`.
- Schema path is fixed:
  - `get_schema()` does not use configuration; it always reads from `src/custom/modules/arxiv_agent/ontologies/ArXivOntology.ttl`.

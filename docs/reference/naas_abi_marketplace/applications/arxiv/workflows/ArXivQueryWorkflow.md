# ArXivQueryWorkflow

## What it is
A workflow that loads local ArXiv RDF/Turtle (`.ttl`) files into an RDFLib graph and provides SPARQL-backed queries to:
- list authors for papers (by ID or title substring)
- list papers (by author name or category substring)
- execute custom SPARQL queries
- retrieve the ArXiv ontology schema file (as Turtle)
- expose these capabilities as LangChain tools and FastAPI endpoints

## Public API

### Configuration
- `ArXivQueryWorkflowConfiguration(storage_path: str = "storage/triplestore/application-level/arxiv")`
  - Directory containing `.ttl` files to load into the combined graph.

### Pydantic parameter models
- `AuthorQueryParameters(paper_id: Optional[str], paper_title: Optional[str])`
  - Inputs for author lookup by paper ID and/or title substring.
- `PaperQueryParameters(author_name: Optional[str], category: Optional[str])`
  - Inputs for paper lookup by author name and/or category substring.
- `SchemaParameters()`
  - No fields (placeholder).
- `SparqlQueryParameters(query: str)`
  - SPARQL query string to execute.

### Workflow
- `class ArXivQueryWorkflow(configuration: ArXivQueryWorkflowConfiguration)`
  - `query_authors(parameters: AuthorQueryParameters) -> Dict[str, Any]`
    - Returns `{"papers": [...]}` with paper `id`, `title`, and unique `authors` list.
    - If neither `paper_id` nor `paper_title` is provided, returns `{"error": ...}`.
  - `query_papers(parameters: PaperQueryParameters) -> Dict[str, Any]`
    - Returns `{"papers": [...]}` with paper `id`, `title`, and optional `pdf_url`.
    - If neither `author_name` nor `category` is provided, returns `{"error": ...}`.
  - `get_schema(parameters: SchemaParameters) -> Dict[str, str]`
    - Reads and returns `{"schema": "<ttl content>"}` from `src/custom/modules/arxiv_agent/ontologies/ArXivOntology.ttl`.
    - If missing, returns `{"error": ...}`.
  - `execute_query(parameters: SparqlQueryParameters) -> Dict[str, Any]`
    - Executes the provided SPARQL query and returns `{"results": [ {var: value, ...}, ... ]}`.
    - On failure returns `{"error": ...}`.
  - `get_frequent_authors() -> Dict[str, Any]`
    - Returns `{"authors": [{"name": str, "paper_count": int}, ...]}` ordered by descending count.
    - On failure returns `{"error": ...}`.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Provides LangChain `StructuredTool`s:
      - `query_arxiv_authors`
      - `query_arxiv_papers`
      - `get_arxiv_schema`
      - `execute_arxiv_query`
      - `get_frequent_authors`
  - `as_api(router: fastapi.APIRouter, ...) -> None`
    - Registers FastAPI routes:
      - `POST /arxiv/query-authors`
      - `POST /arxiv/query-papers`
      - `POST /arxiv/schema`
      - `POST /arxiv/query`

## Configuration/Dependencies
- File storage:
  - Loads all `*.ttl` files from `ArXivQueryWorkflowConfiguration.storage_path`.
- Ontology file:
  - `src/custom/modules/arxiv_agent/ontologies/ArXivOntology.ttl` is read by `get_schema()`.
- Key dependencies (imported):
  - `rdflib` (`Graph`, SPARQL querying)
  - `naas_abi_core.utils.Graph.ABIGraph` (used as combined graph)
  - `fastapi` (`APIRouter`) for `as_api`
  - `langchain_core.tools` (`StructuredTool`) for `as_tools`
  - `pydantic` for request/parameter models

## Usage

### Run queries directly (Python)
```python
from naas_abi_marketplace.applications.arxiv.workflows.ArXivQueryWorkflow import (
    ArXivQueryWorkflow,
    ArXivQueryWorkflowConfiguration,
    AuthorQueryParameters,
    PaperQueryParameters,
    SparqlQueryParameters,
)

wf = ArXivQueryWorkflow(ArXivQueryWorkflowConfiguration(
    storage_path="storage/triplestore/application-level/arxiv"
))

print(wf.query_authors(AuthorQueryParameters(paper_id="2206.11097")))
print(wf.query_papers(PaperQueryParameters(author_name="smith")))
print(wf.execute_query(SparqlQueryParameters(query="""
PREFIX abi: <http://ontology.naas.ai/abi/>
SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5
""")))
```

### Expose as FastAPI endpoints
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
- Graph loading:
  - If `storage_path` does not exist or contains no `.ttl` files, methods return empty result sets (and print warnings to stdout).
  - Per-file parse errors are printed and skipped.
- Query construction:
  - `query_authors()` / `query_papers()` interpolate user input directly into SPARQL strings; malformed input may break queries.
- API coverage:
  - `as_api()` does **not** expose `get_frequent_authors()` as an endpoint (only available via direct call or `as_tools()`).
- Schema path is fixed:
  - `get_schema()` always reads from `src/custom/modules/arxiv_agent/ontologies/ArXivOntology.ttl` (not configurable via workflow configuration).

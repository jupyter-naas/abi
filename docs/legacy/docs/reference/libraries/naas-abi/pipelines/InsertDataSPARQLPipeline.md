# InsertDataSPARQLPipeline

## What it is
- A pipeline that executes a SPARQL `INSERT DATA` statement against an in-memory `rdflib.Graph`, then inserts the resulting triples into a configured triple store (`ITripleStoreService`).
- Includes helper tooling to extract/clean an `INSERT DATA` statement from fenced code blocks (```sparql ... ```).

## Public API
### Classes
- `InsertDataSPARQLPipelineConfiguration(PipelineConfiguration)`
  - **Fields**
    - `triple_store: ITripleStoreService` - target triple store service used for insertion.

- `InsertDataSPARQLPipelineParameters(PipelineParameters)`
  - **Fields**
    - `sparql_statement: str` - SPARQL `INSERT DATA` statement (optionally wrapped in ```sparql fences).

- `InsertDataSPARQLPipeline(Pipeline)`
  - `__init__(configuration: InsertDataSPARQLPipelineConfiguration)`
    - Stores configuration (notably the triple store service).
  - `get_sparql_from_text(parameters: InsertDataSPARQLPipelineParameters) -> str`
    - Strips optional ```sparql fences and returns the text if it contains `"INSERT DATA"`.
    - Otherwise returns a message string indicating no statement was found.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Validates `parameters` type (`InsertDataSPARQLPipelineParameters` required).
    - Creates a new `rdflib.Graph`, binds namespaces (`bfo`, `cco`, `abi`), runs `graph.update(...)`.
    - If triples were inserted (`len(graph) > 0`), calls `configuration.triple_store.insert(graph)`.
    - Returns the resulting `Graph` (or an empty `Graph()` on SPARQL execution failure).
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes two LangChain `StructuredTool`s:
      - `insert_data_sparql`: runs the pipeline with `sparql_statement`.
      - `extract_sparql_from_text`: returns extracted/cleaned SPARQL text.
  - `as_api(...) -> None`
    - Present but does not register any endpoints (no-op; returns `None`).

## Configuration/Dependencies
- Requires an implementation of `naas_abi_core.services.triple_store.TripleStorePorts.ITripleStoreService` with an `insert(graph: rdflib.Graph)` method.
- Uses:
  - `rdflib.Graph` for SPARQL update execution and triple storage before insertion.
  - `langchain_core.tools.StructuredTool` for tool exposure.
- Namespace bindings applied to the graph:
  - `bfo = http://purl.obolibrary.org/obo/`
  - `cco = https://www.commoncoreontologies.org/`
  - `abi = http://ontology.naas.ai/abi/`

## Usage
```python
from naas_abi.pipelines.InsertDataSPARQLPipeline import (
    InsertDataSPARQLPipeline,
    InsertDataSPARQLPipelineConfiguration,
    InsertDataSPARQLPipelineParameters,
)

# Provide a real ITripleStoreService from your environment
triple_store_service = ...  # must implement .insert(rdflib.Graph)

pipeline = InsertDataSPARQLPipeline(
    InsertDataSPARQLPipelineConfiguration(triple_store=triple_store_service)
)

sparql = """
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
INSERT DATA {
  abi:john a owl:NamedIndividual .
}
"""

graph = pipeline.run(InsertDataSPARQLPipelineParameters(sparql_statement=sparql))
print(len(graph))
```

## Caveats
- `run()` only accepts `InsertDataSPARQLPipelineParameters`; otherwise it raises `ValueError`.
- `get_sparql_from_text()` performs a simple substring check for `"INSERT DATA"`; it may return a non-query message string which will later cause `graph.update(...)` to fail and return an empty graph.
- `as_api()` is a no-op (does not expose HTTP endpoints).

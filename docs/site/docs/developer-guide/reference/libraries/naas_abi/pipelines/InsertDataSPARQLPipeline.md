# InsertDataSPARQLPipeline

## What it is
- A `Pipeline` that parses and executes a SPARQL `INSERT DATA` statement against an in-memory `rdflib.Graph`, then inserts the resulting triples into a configured triple store (`ITripleStoreService`).
- Provides LangChain `StructuredTool` wrappers for execution and for extracting the SPARQL from text.

## Public API

### Classes
- `InsertDataSPARQLPipelineConfiguration(PipelineConfiguration)`
  - **Fields**
    - `triple_store: ITripleStoreService` — triple store service used to insert the resulting graph.

- `InsertDataSPARQLPipelineParameters(PipelineParameters)`
  - **Fields**
    - `sparql_statement: str` — SPARQL `INSERT DATA` statement (may be wrapped in Markdown fences).

- `InsertDataSPARQLPipeline(Pipeline)`
  - `__init__(configuration: InsertDataSPARQLPipelineConfiguration)`
    - Stores configuration (notably the triple store service).
  - `get_sparql_from_text(parameters: InsertDataSPARQLPipelineParameters) -> str`
    - Strips ```sparql ... ``` fences if present.
    - Returns the extracted text if it contains `"INSERT DATA"`, otherwise returns a message string indicating none was found.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Validates parameter type (`InsertDataSPARQLPipelineParameters` required).
    - Creates a new `rdflib.Graph` and binds namespaces: `bfo`, `cco`, `abi`.
    - Executes `graph.update(...)` with extracted SPARQL.
    - If graph has triples, inserts it into `configuration.triple_store` via `insert(graph)`.
    - Returns the graph; returns an empty `Graph()` on SPARQL execution failure.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Returns two `StructuredTool`s:
      - `insert_data_sparql` — runs the pipeline with provided args.
      - `extract_sparql_from_text` — returns extracted SPARQL from provided text.
  - `as_api(...) -> None`
    - Present but does not register routes (returns `None`).

## Configuration/Dependencies
- Requires an `ITripleStoreService` instance provided via `InsertDataSPARQLPipelineConfiguration(triple_store=...)`.
- Uses:
  - `rdflib.Graph` for SPARQL updates.
  - `langchain_core.tools.StructuredTool` for tool exposure.
  - `naas_abi_core.logger` for logging.
- Namespace bindings added to the created graph:
  - `bfo = http://purl.obolibrary.org/obo/`
  - `cco = https://www.commoncoreontologies.org/`
  - `abi = http://ontology.naas.ai/abi/`

## Usage

### Minimal example
```python
from naas_abi.pipelines.InsertDataSPARQLPipeline import (
    InsertDataSPARQLPipeline,
    InsertDataSPARQLPipelineConfiguration,
    InsertDataSPARQLPipelineParameters,
)

# Provide an ITripleStoreService implementation
triple_store = ...  # must have .insert(graph)

pipeline = InsertDataSPARQLPipeline(
    InsertDataSPARQLPipelineConfiguration(triple_store=triple_store)
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

### As LangChain tools
```python
tools = pipeline.as_tools()
# tools[0].name == "insert_data_sparql"
# tools[1].name == "extract_sparql_from_text"
```

## Caveats
- `run()` requires `InsertDataSPARQLPipelineParameters`; otherwise it raises `ValueError`.
- `get_sparql_from_text()` only checks for the substring `"INSERT DATA"`; if missing, it returns a message string (not an exception). Passing that message to `graph.update()` will fail and `run()` will return an empty graph.
- `as_api()` is a no-op and does not expose HTTP endpoints.

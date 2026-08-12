# common.py (document pipelines)

## What it is
Utility functions for document ingestion/processing pipelines that query a triple store to:
- Detect whether a file (by SHA-256) has already been ingested into a given RDF graph.
- List files of a given MIME type that have not yet been processed by a specific processor IRI.

## Public API
- `file_already_ingested(sha256: str, graph_name: str) -> bool`
  - Runs a SPARQL query against `graph_name` to check for any `doc:sha256` triple matching `sha256`.
  - Returns `True` if at least one matching file exists; otherwise `False`.

- `get_files_to_process(graph_name: str, mime_type: str, processor_iri: str) -> list[str]`
  - Runs a SPARQL query against `graph_name` to find `?fileIRI` with `doc:mime_type == mime_type`
    and **without** a `doc:processedBy <processor_iri>` triple.
  - Returns a list of file IRIs as strings.

## Configuration/Dependencies
- Depends on `ABIModule.get_instance()` and its triple store service:
  - `module.engine.services.triple_store.query(query)` must exist and return an iterable of result bindings.
- Uses the document ontology prefix:
  - `doc: <http://ontology.naas.ai/abi/document/>`

## Usage
```python
from naas_abi_marketplace.domains.document.pipelines.common import (
    file_already_ingested,
    get_files_to_process,
)

graph = "http://example.org/graphs/documents"

# Check if a file hash is already present in the graph
exists = file_already_ingested(
    sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    graph_name=graph,
)

# List files that match a MIME type and haven't been processed by a processor IRI
pending = get_files_to_process(
    graph_name=graph,
    mime_type="application/pdf",
    processor_iri="http://example.org/processors/pdf-extractor",
)

print(exists, pending)
```

## Caveats
- Both functions build SPARQL queries via string interpolation; inputs should be trusted/validated to avoid malformed queries.
- `file_already_ingested` materializes results with `list(results)` to count them; on large result sets this may be inefficient.

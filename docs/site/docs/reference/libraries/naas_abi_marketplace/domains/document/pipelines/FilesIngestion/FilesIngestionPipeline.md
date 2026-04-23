# FilesIngestionPipeline

## What it is
A pipeline that lists file objects from an object-storage prefix, uploads each file into the document knowledge graph (as `File` resources), and optionally deletes the source objects after ingestion.

## Public API

- `FilesIngestionPipelineConfiguration(PipelineConfiguration)`
  - Configuration container for the pipeline (currently no additional fields).

- `FilesIngestionPipelineParameters(PipelineParameters)`
  - `input_path: str`: Object-storage prefix to ingest (recursive).
  - `output_path: str`: Destination directory/prefix where ingested files should be saved.
  - `graph_name: str` (default: `"http://ontology.naas.ai/graph/document"`): Target RDF graph IRI.
  - `recursive: bool` (default: `True`): Whether to traverse prefixes recursively.
  - `processor_iri: str` (default: `"http://ontology.naas.ai/abi/document/FileIngestionProcessor"`): IRI recorded as processor.
  - `delete_from_input: bool` (default: `False`): Delete source objects after ingestion (also applies to already-ingested files).

- `FilesIngestionPipeline(Pipeline)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Lists objects under `input_path`, fetches content and metadata, deduplicates by SHA-256 (via `file_already_ingested`), creates/uploads `File` resources, returns an RDFLib `Graph` containing the generated triples.
  - `as_tools() -> list[BaseTool]`
    - Returns an empty list.
  - `as_api()`
    - Declared but not implemented (`pass`).

## Configuration/Dependencies

- Requires an initialized `ABIModule` (singleton via `ABIModule.get_instance()`) providing:
  - `engine.services.object_storage` with:
    - `list_objects(prefix=...)`
    - `get_object(prefix="", key=...)`
    - `get_object_metadata(prefix="", key=...)`
    - `delete_object(prefix="", key=...)`
  - `engine.services.triple_store` is referenced by a private helper (`__ensure_graph_exists`) but not used in `run()`.

- Uses:
  - `file_already_ingested(sha256: str, graph_name: str)` for deduplication.
  - `File.UploadAndCreateFile(...)` to create/upload and emit RDF triples.
  - `rdflib.Graph` for output.

## Usage

```python
from naas_abi_marketplace.domains.document.pipelines.FilesIngestion.FilesIngestionPipeline import (
    FilesIngestionPipeline,
    FilesIngestionPipelineConfiguration,
    FilesIngestionPipelineParameters,
)

pipeline = FilesIngestionPipeline(FilesIngestionPipelineConfiguration())

g = pipeline.run(
    FilesIngestionPipelineParameters(
        input_path="documents/my_folder",
        output_path="ingested/documents",
        graph_name="http://ontology.naas.ai/graph/document",
        recursive=True,
        delete_from_input=False,
    )
)

print(g.serialize(format="turtle"))
```

## Caveats

- `run()` requires `FilesIngestionPipelineParameters`; otherwise it raises `ValueError`.
- Listing treats object storage keys as POSIX-like paths; directory detection depends on `list_objects()` behavior and may probe entries by attempting to list them as prefixes.
- The pipeline computes SHA-256 by downloading full object content; large objects may be expensive.
- `graph_name` is annotated as `str`, but the `__main__` example passes an `rdflib.URIRef`; ensure your call site matches what your pipeline framework expects.
- Graph creation is not ensured during `run()`; the private `__ensure_graph_exists()` is defined but not invoked.

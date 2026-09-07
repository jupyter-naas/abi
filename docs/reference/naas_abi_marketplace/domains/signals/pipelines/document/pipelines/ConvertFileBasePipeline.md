# ConvertFileBasePipeline

## What it is
- A base `Pipeline` for converting files of a given MIME type into another format and registering the converted file back into a triple-store-backed document graph.
- Designed to be subclassed: the actual conversion logic must be implemented in `convert()`.

## Public API
### Classes
- `ConvertFileBasePipelineConfiguration(PipelineConfiguration)`
  - `mime_type: str` — MIME type of input files to convert.
  - `output_mime_type: str` — MIME type of converted output files.
  - `output_extension: str` — Extension appended to converted filenames (including the dot).

- `ConvertFileBasePipelineParameters(PipelineParameters)`
  - `graph_name: str = "http://ontology.naas.ai/graph/document"` — target graph name.
  - `processor_iri: str` — IRI of the processor performing the conversion (used for provenance).

- `ConvertFileBasePipeline(Pipeline)`
  - `__init__(configuration)` — stores configuration and retrieves `ABIModule` singleton.
  - `convert(file: File) -> str` — **abstract**; must be implemented by subclasses to return converted content as a string.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Finds files to process via `get_files_to_process(graph_name, mime_type, processor_iri)`.
    - For each file:
      - Loads `File` from the triple store.
      - Converts content via `self.convert(f)`.
      - Uploads and creates a new `File` with:
        - `filename = original_name + output_extension`
        - `destination_path = dirname(original_file_path)`
        - `mime_type = output_mime_type`
        - provenance: `derivedFrom` original file IRI, `processedBy` processor IRI
      - Updates original file’s `processedBy` list to include `processor_iri` (if missing).
      - Inserts updated original `File` RDF into the triple store.
      - Returns an `rdflib.Graph` containing RDF for both the new file and updated original file.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `"ConvertFileBase"`.
  - `as_api(...) -> None`
    - Currently a stub that does nothing.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.pipeline` (`Pipeline`, `PipelineConfiguration`, `PipelineParameters`)
  - `ABIModule.get_instance()` and its triple store service:
    - `module.engine.services.triple_store.query`
    - `module.engine.services.triple_store.insert`
  - Ontology-backed `File` class:
    - `File.from_iri(...)`
    - `File.UploadAndCreateFile(...)`
    - `File.rdf()`
  - `get_files_to_process(graph_name, mime_type, processor_iri)`
  - `rdflib.Graph`
- Storage behavior:
  - Converted files are uploaded to the directory of the original file (`os.path.dirname(f.file_path)`).

## Usage
Minimal subclass example (conversion logic is up to you):

```python
from naas_abi_marketplace.domains.signals.pipelines.document.pipelines.ConvertFileBasePipeline import (
    ConvertFileBasePipeline,
    ConvertFileBasePipelineConfiguration,
    ConvertFileBasePipelineParameters,
)

class UppercaseTextPipeline(ConvertFileBasePipeline):
    def convert(self, file):
        # Implement conversion; return converted content as str.
        # (Actual access to file content depends on the File model; not shown here.)
        return "converted content"

cfg = ConvertFileBasePipelineConfiguration(
    mime_type="text/plain",
    output_mime_type="text/plain",
    output_extension=".converted.txt",
)

pipeline = UppercaseTextPipeline(cfg)

result_graph = pipeline.run(
    ConvertFileBasePipelineParameters(
        processor_iri="http://example.org/processors/uppercase"
    )
)
```

Using as a LangChain tool:

```python
tool = pipeline.as_tools()[0]
# tool expects kwargs matching ConvertFileBasePipelineParameters
tool.invoke({"processor_iri": "http://example.org/processors/uppercase"})
```

## Caveats
- `convert()` is not implemented; calling `run()` on `ConvertFileBasePipeline` directly raises `NotImplementedError`.
- `run()` asserts `parameters` is a `ConvertFileBasePipelineParameters` instance.
- `as_api()` is a no-op (does not register routes).

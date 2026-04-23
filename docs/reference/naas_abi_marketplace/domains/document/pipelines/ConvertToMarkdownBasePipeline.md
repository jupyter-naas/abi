# ConvertToMarkdownBasePipeline

## What it is
- An abstract `Pipeline` that finds files of a given MIME type in an RDF graph, converts each to Markdown (via a subclass implementation), uploads the resulting `.md` file, and returns RDF statements describing the new files.

## Public API

### Classes

- `ConvertToMarkdownBasePipelineConfiguration(PipelineConfiguration)`
  - `mime_type: str`
    - MIME type used to select which files to convert.

- `ConvertToMarkdownBasePipelineParameters(PipelineParameters)`
  - `graph_name: str = "http://ontology.naas.ai/graph/document"`
    - Graph name to read from / ingest into.
  - `processor_iri: str`
    - IRI of the processor used to mark files as processed.

- `ConvertToMarkdownBasePipeline(Pipeline)`
  - `__init__(configuration: ConvertToMarkdownBasePipelineConfiguration)`
    - Stores configuration and resolves `ABIModule` singleton.
  - `convert_to_markdown(file: File) -> str`
    - **Abstract**; must be implemented by subclasses to produce Markdown content for a `File`.
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Pipeline execution:
      - Selects files via `get_files_to_process(graph_name, mime_type, processor_iri)`.
      - For each file IRI:
        - Loads `File` from triple store.
        - Calls `convert_to_markdown`.
        - Uploads and creates a new `.md` `File` via `File.UploadAndCreateFile(...)`.
        - Adds `derivedFrom` and `processedBy` links.
      - Returns an RDF `Graph` containing new file triples.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `"ConvertToMarkdownBase"`.
  - `as_api(...) -> None`
    - No-op (returns `None`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.pipeline` (`Pipeline`, `PipelineConfiguration`, `PipelineParameters`)
  - `rdflib.Graph`
  - `naas_abi_marketplace.domains.document.ABIModule` (triple store access)
  - `File` ontology class:
    - `File.from_iri(...)`
    - `File.UploadAndCreateFile(...)`
    - `new_file.rdf()`
  - `get_files_to_process(...)` (selects file IRIs to process)
  - LangChain tooling (`StructuredTool`)
- `mime_type` drives which files are considered for conversion.

## Usage

```python
from naas_abi_marketplace.domains.document.pipelines.ConvertToMarkdownBasePipeline import (
    ConvertToMarkdownBasePipeline,
    ConvertToMarkdownBasePipelineConfiguration,
    ConvertToMarkdownBasePipelineParameters,
)

class MyMarkdownPipeline(ConvertToMarkdownBasePipeline):
    def convert_to_markdown(self, file):
        # Implement actual conversion logic here
        return f"# {file.file_name}\n\nConverted content."

pipeline = MyMarkdownPipeline(
    ConvertToMarkdownBasePipelineConfiguration(mime_type="application/pdf")
)

result_graph = pipeline.run(
    ConvertToMarkdownBasePipelineParameters(
        processor_iri="http://example.org/processors/convert-to-md"
    )
)
```

## Caveats
- `convert_to_markdown` is not implemented and will raise `NotImplementedError` unless overridden.
- `run()` asserts parameters are `ConvertToMarkdownBasePipelineParameters`; passing other parameter types will fail.
- `as_api()` does not register any routes (no API exposure by default).

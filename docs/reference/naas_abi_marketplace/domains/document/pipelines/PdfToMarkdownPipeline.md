# PdfToMarkdownPipeline

## What it is
- A pipeline that converts PDF (`application/pdf`) files into Markdown text.
- Implements conversion by writing the file bytes to a temporary file and using `pymupdf4llm.to_markdown(...)`.

## Public API
- `PdfToMarkdownPipelineConfiguration`
  - Extends `ConvertToMarkdownBasePipelineConfiguration`.
  - `mime_type: str` — defaults to `"application/pdf"`.

- `PdfToMarkdownPipelineParameters`
  - Extends `ConvertToMarkdownBasePipelineParameters`.
  - `processor_iri: str` — defaults to `"http://ontology.naas.ai/abi/document/PDFToMarkdownProcessor"`.

- `PdfToMarkdownPipeline`
  - Extends `ConvertToMarkdownBasePipeline`.
  - `__init__(configuration: PdfToMarkdownPipelineConfiguration)`
    - Initializes the base pipeline and retrieves the `ABIModule` singleton via `ABIModule.get_instance()`.
  - `convert_to_markdown(file: File) -> str`
    - Reads file content (`file.read()`), writes it to a temporary file, converts it to Markdown via `pymupdf4llm.to_markdown(temp_path)`, deletes the temp file, and returns the Markdown string.

## Configuration/Dependencies
- Depends on:
  - `pymupdf4llm` for PDF-to-Markdown conversion.
  - `naas_abi_marketplace.domains.document.ABIModule` (singleton access).
  - `File` from the document ontology (`file.read()` must return bytes).
  - Base pipeline types:
    - `ConvertToMarkdownBasePipeline`
    - `ConvertToMarkdownBasePipelineConfiguration`
    - `ConvertToMarkdownBasePipelineParameters`
  - `pydantic.Field` / `typing.Annotated` for parameter metadata.

## Usage
```python
from naas_abi_marketplace.domains.document.pipelines.PdfToMarkdownPipeline import (
    PdfToMarkdownPipeline,
    PdfToMarkdownPipelineConfiguration,
)

# 'file' must be an instance of the ontology File class with a .read() -> bytes method.
pipeline = PdfToMarkdownPipeline(PdfToMarkdownPipelineConfiguration())
markdown_text = pipeline.convert_to_markdown(file)
print(markdown_text)
```

## Caveats
- The conversion writes the PDF bytes to a temporary file on disk (`tempfile.NamedTemporaryFile(delete=False)`).
- Temporary file cleanup is performed after conversion (`os.unlink`); if conversion raises an exception before cleanup, the temporary file may remain on disk.

# PptxToMarkdownPipeline

## What it is
A pipeline that converts a `.pptx` (PowerPoint) file into Markdown by extracting text from each slide’s XML and formatting it as slide headers with bullet points.

## Public API
- `PptxToMarkdownPipelineConfiguration`
  - `mime_type: str` — MIME type this pipeline targets. Default:
    - `application/vnd.openxmlformats-officedocument.presentationml.presentation`
- `PptxToMarkdownPipelineParameters`
  - `processor_iri: str` — IRI identifying the processor. Default:
    - `http://ontology.naas.ai/abi/document/PptxToMarkdownProcessor`
- `PptxToMarkdownPipeline`
  - `convert_to_markdown(file: File) -> str` — Reads PPTX content from `file`, extracts slide text, and returns Markdown.
  - Internal helpers (not intended as public API):
    - `_normalize_whitespace(value: str) -> str`
    - `_list_slide_paths(pptx_file: zipfile.ZipFile) -> list[str]`
    - `_extract_text_from_slide(slide_xml: bytes) -> list[str]`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace...File` providing `read() -> bytes`
  - Base classes:
    - `ConvertToMarkdownBasePipeline`
    - `ConvertToMarkdownBasePipelineConfiguration`
    - `ConvertToMarkdownBasePipelineParameters`
  - Standard library: `zipfile`, `io`, `re`, `xml.etree.ElementTree`
  - `pydantic.Field` for parameter metadata

## Usage
```python
from naas_abi_marketplace.domains.document.pipelines.PptxToMarkdownPipeline import (
    PptxToMarkdownPipeline,
)
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import File

pipeline = PptxToMarkdownPipeline()

pptx_file: File = ...  # must implement .read() returning PPTX bytes
md = pipeline.convert_to_markdown(pptx_file)
print(md)
```

Markdown output shape:
- For each non-empty slide:
  - `## Slide N`
  - `- <line 1>`
  - `- <line 2>`
  - ...

## Caveats
- Only extracts text present in slide XML text runs (`a:t`) and treats line breaks (`a:br`) as newline markers before whitespace normalization.
- Images, tables, speaker notes, and most formatting are not converted.
- If the input is not a valid PPTX zip (or slide XML cannot be read), `convert_to_markdown` raises `ValueError("Invalid PPTX content: unable to read slide XML")`.
- Slide numbering is derived from `ppt/slides/slide*.xml` filenames and sorted by their numeric index.

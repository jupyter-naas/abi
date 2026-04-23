# DocxToMarkdownPipeline

## What it is
A document conversion pipeline that reads a DOCX file and produces Markdown by extracting paragraphs from `word/document.xml` and mapping basic Word paragraph styles (headings, lists) to Markdown syntax.

## Public API
- `DocxToMarkdownPipelineConfiguration`
  - Extends `ConvertToMarkdownBasePipelineConfiguration`.
  - `mime_type`: Defaults to `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.

- `DocxToMarkdownPipelineParameters`
  - Extends `ConvertToMarkdownBasePipelineParameters`.
  - `processor_iri`: Defaults to `http://ontology.naas.ai/abi/document/DocxToMarkdownProcessor`.

- `DocxToMarkdownPipeline`
  - Extends `ConvertToMarkdownBasePipeline`.
  - `convert_to_markdown(file: File) -> str`: Converts a DOCX `File` to a Markdown string.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.domains.document.pipelines.ConvertToMarkdownBasePipeline` (base classes/config/params)
  - `naas_abi_marketplace...File` for reading file bytes (`file.read()` must return `bytes`)
  - Standard libs: `zipfile`, `xml.etree.ElementTree`, `re`, `io`
  - `pydantic.Field` and `typing.Annotated` for configuration metadata

## Usage
```python
from naas_abi_marketplace.domains.document.pipelines.DocxToMarkdownPipeline import (
    DocxToMarkdownPipeline,
)
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import (
    File,
)

pipeline = DocxToMarkdownPipeline()
docx_file: File = ...  # must support .read() -> bytes for a DOCX
markdown = pipeline.convert_to_markdown(docx_file)
print(markdown)
```

## Caveats
- Only processes `word/document.xml`; invalid DOCX content or missing `word/document.xml` raises `ValueError("Invalid DOCX content: missing word/document.xml")`.
- Markdown conversion is minimal:
  - Headings: only paragraph styles matching `Heading1`…`Heading6`.
  - Lists: any paragraph with numbering properties (`w:numPr`) becomes `- ...` (no ordered list numbering).
  - Inline formatting (bold/italic/links/images/tables) is not handled; text is extracted from `w:t` nodes only.
- Whitespace normalization collapses runs of spaces/tabs to a single space and trims ends; explicit `w:tab` becomes four spaces and `w:br`/`w:cr` become newline characters (which may be normalized).

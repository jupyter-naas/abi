# PdfToHtmlPipeline

## What it is
- A document-conversion pipeline that converts **PDF** files into a **single self-contained HTML** document.
- Uses **docling** to extract structured content and **embeds images** in the HTML output.
- Wraps each PDF page in a `<section class="pdf-page" data-page="N">...</section>` block for downstream page-aware processing.
- Optionally calls a **vision-capable LLM** (OpenAI-compatible endpoint) to generate picture descriptions and embed them as `<figcaption>` during HTML export.

## Public API
- `PdfToHtmlPipelineConfiguration`
  - Configuration values for PDF → HTML conversion (MIME types, image scale, optional image captioning via remote API).
- `PdfToHtmlPipelineParameters`
  - Declares `processor_iri` identifying the processor used for ingestion/processing metadata.
- `PdfToHtmlPipeline`
  - `__init__(configuration: PdfToHtmlPipelineConfiguration)`
    - Initializes the pipeline and builds docling `PdfPipelineOptions`.
  - `convert(file: File) -> str`
    - Reads the input `File`, converts the PDF to HTML, and returns the resulting HTML string.

## Configuration/Dependencies
### Key dependencies
- `docling` / `docling_core`
  - `DocumentConverter`, `PdfPipelineOptions`, `PictureDescriptionApiOptions`
  - `HTMLDocSerializer`, `HTMLParams`, `ImageRefMode`
- Internal types
  - `File` (expects `.read()` and `.file_name`)
  - `ConvertFileBasePipeline` and related configuration/parameters base classes

### `PdfToHtmlPipelineConfiguration` fields (selected)
- Conversion defaults
  - `mime_type`: `"application/pdf"`
  - `output_mime_type`: `"text/html"`
  - `output_extension`: `".html"`
  - `images_scale`: `2.0` (embedded image resolution scale; `1.0` = native)
- Optional picture description via remote vision LLM (disabled when API key is empty)
  - `image_description_api_key`: `""` (empty disables captioning)
  - `image_description_base_url`: `"https://openrouter.ai/api/v1/chat/completions"`
  - `image_description_model`: `"google/gemini-2.0-flash-001"`
  - `image_description_prompt`: prompt string used per image
  - `image_description_concurrency`: `4`
  - `image_description_timeout_seconds`: `30.0`
  - `image_description_picture_area_threshold`: `0.05`
- When `image_description_api_key` is set:
  - `opts.do_picture_description = True`
  - `opts.enable_remote_services = True`
  - Authorization header is sent as `Bearer <api_key>`

## Usage
```python
from naas_abi_marketplace.domains.signals.pipelines.document.pipelines.PdfToHtmlPipeline import (
    PdfToHtmlPipeline,
    PdfToHtmlPipelineConfiguration,
)

# `File` must be an instance of the project File class:
# - file.read() -> bytes (PDF content)
# - file.file_name -> str
from naas_abi_marketplace.domains.signals.pipelines.document.ontologies.classes.ontology_demo.abi.document.File import File

cfg = PdfToHtmlPipelineConfiguration(
    images_scale=2.0,
    # image_description_api_key="...",  # enable if you want figcaptions via remote vision model
)

pipeline = PdfToHtmlPipeline(cfg)

pdf_file: File = ...  # provide a valid File instance
html = pipeline.convert(pdf_file)

with open("output.html", "w", encoding="utf-8") as f:
    f.write(html)
```

## Caveats
- Conversion writes the PDF bytes to a **temporary `.pdf` file** because docling converts from a filesystem path.
- If `image_description_api_key` is set, the pipeline enables **remote service calls** (vision API) and sends the API key as a bearer token.

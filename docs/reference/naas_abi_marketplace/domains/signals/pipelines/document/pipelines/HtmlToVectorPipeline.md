# HtmlToVectorPipeline

## What it is
A document pipeline that:
- Parses HTML content.
- Splits it into layout-aware text chunks (optionally per PDF page via `<section data-page="N">`).
- Produces chunk objects with per-chunk metadata (e.g., `page_number`) for downstream vector storage via the base pipeline.

## Public API
- `class HtmlToVectorPipeline(ToVectorBasePipeline)`
  - `chunk_content(content: bytes, file_path: str) -> list[ChunkInfo]`
    - Decodes HTML (`utf-8`, `errors="replace"`) and chunks it using internal HTML splitting logic.
    - Returns `ChunkInfo(text=..., extra_metadata=...)` for each chunk.

- `@dataclass class HtmlToVectorPipelineConfiguration(ToVectorBasePipelineConfiguration)`
  - `mime_type: str = "text/html"`
    - Declares the expected MIME type for this pipeline.

- `class HtmlToVectorPipelineParameters(ToVectorBasePipelineParameters)`
  - `graph_name: str = "http://ontology.naas.ai/graph/document"`
    - RDF graph name containing the document triples.

## Configuration/Dependencies
- Depends on:
  - `bs4` (`BeautifulSoup`, `Tag`) for HTML parsing.
  - Base types from `ToVectorBasePipeline`:
    - `ToVectorBasePipeline`, `ChunkInfo`, `ToVectorBasePipelineConfiguration`, `ToVectorBasePipelineParameters`.
  - `pydantic.Field` for parameter metadata.
- Chunking behavior is governed by the base configuration values:
  - `chunk_size`
  - `chunk_overlap`

## Usage
Minimal example using the internal splitter (useful for testing chunking behavior):

```python
from naas_abi_marketplace.domains.signals.pipelines.document.pipelines.HtmlToVectorPipeline import _split_html

html = """
<body>
  <section class="pdf-page" data-page="1">
    <h1>Title</h1>
    <p>Intro text.</p>
  </section>
  <section class="pdf-page" data-page="2">
    <h2>Next</h2>
    <p>More text.</p>
  </section>
</body>
"""

chunks = _split_html(html, chunk_size=200, chunk_overlap=20)
for text, metadata in chunks:
    print(metadata, text)
```

## Caveats
- Page metadata is only added when the HTML contains `<section data-page="N">` elements; otherwise the whole body is treated as one section with empty metadata.
- `<img>` tags are removed before extracting text to avoid base64/noise; related `<figcaption>` text is preserved as normal text.
- Headings (`h1`–`h6`) force chunk boundaries; oversized single blocks are hard-split into fixed-size slices using `chunk_size` and `chunk_overlap`.

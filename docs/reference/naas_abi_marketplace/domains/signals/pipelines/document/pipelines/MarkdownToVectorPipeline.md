# MarkdownToVectorPipeline

## What it is
A document-to-vector pipeline for Markdown (`text/markdown`) that:
- Decodes Markdown bytes as UTF-8
- Splits text into overlapping chunks while respecting Markdown structure
- Produces `ChunkInfo` objects for downstream embedding/vector-store handling (via `ToVectorBasePipeline`)

## Public API
- `class MarkdownToVectorPipeline(ToVectorBasePipeline)`
  - `chunk_content(self, content: bytes, file_path: str) -> list[ChunkInfo]`
    - Decodes `content` as UTF-8 (with replacement on errors) and returns chunked `ChunkInfo` items using `_split_markdown`.

- `@dataclass class MarkdownToVectorPipelineConfiguration(ToVectorBasePipelineConfiguration)`
  - `mime_type: str = "text/markdown"`
    - Declares the handled MIME type.

- `class MarkdownToVectorPipelineParameters(ToVectorBasePipelineParameters)`
  - `graph_name: str = "http://ontology.naas.ai/graph/document"`
    - RDF graph name containing document triples.

- `_split_markdown(text: str, chunk_size: int, chunk_overlap: int) -> list[str]` (module helper)
  - Splitting strategy (in order):
    - Prefer heading boundaries (`#`..`######`)
    - Then paragraph boundaries (blank lines)
    - Then enforce hard character limit using a sliding window with overlap

## Configuration/Dependencies
- Depends on:
  - `ToVectorBasePipeline`, `ChunkInfo`, and base configuration/parameters types from:
    - `naas_abi_marketplace.domains.signals.pipelines.document.pipelines.ToVectorBasePipeline`
  - `pydantic.Field` (used in parameters definition)
- Configuration values used by chunking:
  - `chunk_size` and `chunk_overlap` (from `ToVectorBasePipelineConfiguration`)
  - `mime_type` is set to `text/markdown` in `MarkdownToVectorPipelineConfiguration`

## Usage
Minimal example calling the chunker directly (no vector store wiring shown here):

```python
from naas_abi_marketplace.domains.signals.pipelines.document.pipelines.MarkdownToVectorPipeline import (
    MarkdownToVectorPipeline,
)

pipeline = MarkdownToVectorPipeline()

md = b"# Title\n\nParagraph one.\n\n## Section\n\nParagraph two."
chunks = pipeline.chunk_content(md, file_path="doc.md")

for c in chunks:
    print(c.text)
```

## Caveats
- Input is decoded using UTF-8 with `errors="replace"`; invalid byte sequences will be replaced.
- The final hard-splitting step uses `range(0, len(chunk), chunk_size - chunk_overlap)`:
  - `chunk_overlap` should be `< chunk_size` to avoid invalid/zero step sizes.

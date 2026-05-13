"""Pipeline that chunks HTML files (typically produced by ``PdfToHtmlPipeline``)
and stores embeddings in a vector store.

The chunker is layout-aware: it walks each ``<section class="pdf-page"
data-page="N">`` so every chunk carries its source page number as metadata
(used downstream for citation: "see page 8"). Inside a section, the chunker
prefers splitting on heading boundaries and then enforces a hard character
limit with overlap. ``<img>`` tags are stripped (their ``<figcaption>``
sibling text is already semantically rich thanks to docling); ``<table>``
elements are kept whole when possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from bs4 import BeautifulSoup, Tag
from naas_abi_marketplace.domains.document.pipelines.ToVectorBasePipeline import (
    ChunkInfo,
    ToVectorBasePipeline,
    ToVectorBasePipelineConfiguration,
    ToVectorBasePipelineParameters,
)
from pydantic import Field

HTML_PROCESSOR_IRI = "http://ontology.naas.ai/abi/document/HtmlToVectorProcessor"

# Heading tags that act as natural split boundaries inside a page section.
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
# Block-level tags whose text we keep as-is when serialising a chunk.
_BLOCK_TAGS = {"p", "ul", "ol", "li", "table", "figure", "figcaption", "blockquote"}


# ---------------------------------------------------------------------------
# HTML chunking
# ---------------------------------------------------------------------------


def _element_text(element: Tag) -> str:
    """Return the cleaned text content of a single HTML element.

    Strips ``<img>`` nodes (they would contribute base64 noise) but keeps
    their ``<figcaption>`` siblings.
    """
    for img in element.find_all("img"):
        img.decompose()
    return element.get_text(" ", strip=True)


def _split_section(
    section: Tag, chunk_size: int, chunk_overlap: int
) -> list[str]:
    """Split a ``<section data-page="N">`` element into text chunks.

    Walks the section's top-level block children in document order. Headings
    flush the current chunk so each new heading starts a new chunk.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        text = "\n\n".join(current).strip()
        if text:
            chunks.append(text)
        # Overlap: carry the tail of the flushed chunk into the next one.
        if chunk_overlap > 0 and text:
            tail = text[-chunk_overlap:]
            current = [tail]
            current_len = len(tail)
        else:
            current = []
            current_len = 0

    for child in section.find_all(recursive=False):
        if not isinstance(child, Tag):
            continue
        tag = child.name.lower()
        if tag not in _BLOCK_TAGS and tag not in _HEADING_TAGS and tag != "div":
            continue

        # Headings start a new chunk
        if tag in _HEADING_TAGS:
            flush()

        text = _element_text(child)
        if not text:
            continue

        # If the single block is larger than chunk_size, hard-split it.
        if len(text) > chunk_size:
            flush()
            for start in range(0, len(text), max(1, chunk_size - chunk_overlap)):
                part = text[start : start + chunk_size]
                if part.strip():
                    chunks.append(part.strip())
            continue

        # Would exceed the limit if we keep accumulating → flush first.
        if current_len + len(text) + 2 > chunk_size:
            flush()

        current.append(text)
        current_len += len(text) + 2  # +2 for the "\n\n" joiner

    flush()
    return chunks


def _split_html(
    html: str, chunk_size: int, chunk_overlap: int
) -> list[tuple[str, dict]]:
    """Parse *html* and return ``(text, metadata)`` for each chunk.

    The metadata dict carries ``page_number`` when the parent section has a
    ``data-page`` attribute. When the HTML has no per-page sections, the
    whole body is treated as a single section.
    """
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup

    page_sections = body.find_all("section", attrs={"data-page": True})
    if page_sections:
        sections: list[tuple[Tag, dict]] = []
        for section in page_sections:
            try:
                page_number = int(section.get("data-page"))
                metadata: dict = {"page_number": page_number}
            except (TypeError, ValueError):
                metadata = {}
            sections.append((section, metadata))
    else:
        # Fall back: treat the entire body as a single section, no page metadata.
        sections = [(body, {})]

    out: list[tuple[str, dict]] = []
    for section, metadata in sections:
        for chunk_text in _split_section(section, chunk_size, chunk_overlap):
            out.append((chunk_text, dict(metadata)))
    return out


# ---------------------------------------------------------------------------
# Pipeline configuration / parameters
# ---------------------------------------------------------------------------


@dataclass
class HtmlToVectorPipelineConfiguration(ToVectorBasePipelineConfiguration):
    """Static configuration for the HtmlToVector pipeline."""

    mime_type: str = field(default="text/html")


class HtmlToVectorPipelineParameters(ToVectorBasePipelineParameters):
    graph_name: Annotated[
        str,
        Field(description="The RDF graph name that contains the document triples."),
    ] = "http://ontology.naas.ai/graph/document"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class HtmlToVectorPipeline(ToVectorBasePipeline):
    """HTML-specific :class:`ToVectorBasePipeline` — chunking happens via
    :func:`_split_html`, which preserves per-page metadata when the HTML
    is structured with ``<section data-page="N">`` markers (as produced by
    :class:`PdfToHtmlPipeline`).
    """

    def chunk_content(self, content: bytes, file_path: str) -> list[ChunkInfo]:
        cfg = self._configuration
        html = content.decode("utf-8", errors="replace")
        return [
            ChunkInfo(text=text, extra_metadata=metadata)
            for text, metadata in _split_html(html, cfg.chunk_size, cfg.chunk_overlap)
        ]

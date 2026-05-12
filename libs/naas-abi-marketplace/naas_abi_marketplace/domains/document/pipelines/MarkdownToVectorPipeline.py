"""Pipeline that chunks Markdown files and stores embeddings in a vector store."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Annotated

from naas_abi_marketplace.domains.document.pipelines.ToVectorBasePipeline import (
    ChunkInfo,
    ToVectorBasePipeline,
    ToVectorBasePipelineConfiguration,
    ToVectorBasePipelineParameters,
)
from pydantic import Field

MARKDOWN_PROCESSOR_IRI = (
    "http://ontology.naas.ai/abi/document/MarkdownToVectorProcessor"
)


# ---------------------------------------------------------------------------
# Markdown text splitter
# ---------------------------------------------------------------------------


def _split_markdown(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split *text* into overlapping chunks of at most *chunk_size* characters.

    The strategy respects Markdown structure by preferring splits at:
    1. heading boundaries (``# …``)
    2. blank lines (paragraph boundaries)
    3. hard character limit with *chunk_overlap* sliding window
    """
    if not text.strip():
        return []

    heading_re = re.compile(r"(?=\n#{1,6} )")
    primary_blocks: list[str] = [b for b in heading_re.split(text) if b.strip()]

    paragraph_blocks: list[str] = []
    for block in primary_blocks:
        if len(block) <= chunk_size:
            paragraph_blocks.append(block)
        else:
            paras = re.split(r"\n\n+", block)
            paragraph_blocks.extend(p for p in paras if p.strip())

    chunks: list[str] = []
    current = ""
    for para in paragraph_blocks:
        if not para.strip():
            continue
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= chunk_size:
            current = current + "\n\n" + para
        else:
            chunks.append(current.strip())
            overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = (overlap_text + "\n\n" + para).strip() if overlap_text else para

    if current.strip():
        chunks.append(current.strip())

    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= chunk_size:
            result.append(chunk)
        else:
            for start in range(0, len(chunk), chunk_size - chunk_overlap):
                part = chunk[start : start + chunk_size]
                if part.strip():
                    result.append(part.strip())

    return result


# ---------------------------------------------------------------------------
# Pipeline configuration / parameters
# ---------------------------------------------------------------------------


@dataclass
class MarkdownToVectorPipelineConfiguration(ToVectorBasePipelineConfiguration):
    """Static configuration for the MarkdownToVector pipeline."""

    mime_type: str = field(default="text/markdown")


class MarkdownToVectorPipelineParameters(ToVectorBasePipelineParameters):
    graph_name: Annotated[
        str,
        Field(description="The RDF graph name that contains the document triples."),
    ] = "http://ontology.naas.ai/graph/document"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class MarkdownToVectorPipeline(ToVectorBasePipeline):
    """Markdown-specific :class:`ToVectorBasePipeline` — chunking happens via
    :func:`_split_markdown` which respects Markdown structure (headings,
    paragraphs, then a hard size limit).
    """

    def chunk_content(self, content: bytes, file_path: str) -> list[ChunkInfo]:
        cfg = self._configuration
        text = content.decode("utf-8", errors="replace")
        return [
            ChunkInfo(text=t)
            for t in _split_markdown(text, cfg.chunk_size, cfg.chunk_overlap)
        ]

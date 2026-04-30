"""Pipeline that chunks Markdown files and stores embeddings in a vector store.

Cache key format: ``{model_id}_{dimension}_{sha256_hex(text.encode())}``
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated

import numpy as np
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import OpenAIEmbeddings
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.utils.Expose import APIRouter
from pydantic import Field
from rdflib import Graph, URIRef

from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import (
    Chunk,
)

MARKDOWN_PROCESSOR_IRI = (
    "http://ontology.naas.ai/abi/document/MarkdownToVectorProcessor"
)
DEFAULT_COLLECTION = "documents"
DEFAULT_MODEL_ID = "text-embedding-3-small"
DEFAULT_DIMENSION = 1536
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


# ---------------------------------------------------------------------------
# Simple Markdown text splitter (no external langchain_text_splitters needed)
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

    # First pass: split on headings or double newlines
    heading_re = re.compile(r"(?=\n#{1,6} )")
    primary_blocks: list[str] = [b for b in heading_re.split(text) if b.strip()]

    # Second pass: further split large blocks on paragraph boundaries
    paragraph_blocks: list[str] = []
    for block in primary_blocks:
        if len(block) <= chunk_size:
            paragraph_blocks.append(block)
        else:
            paras = re.split(r"\n\n+", block)
            paragraph_blocks.extend(p for p in paras if p.strip())

    # Third pass: merge small fragments and enforce chunk_size limit
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
            # Overlap: carry the last *chunk_overlap* characters from the current chunk
            overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = (overlap_text + "\n\n" + para).strip() if overlap_text else para

    if current.strip():
        chunks.append(current.strip())

    # Final guard: hard-split any chunk that is still too large
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
class MarkdownToVectorPipelineConfiguration(PipelineConfiguration):
    """Static configuration for the MarkdownToVector pipeline."""

    collection_name: str = field(default=DEFAULT_COLLECTION)
    file_path: str = field(default="")
    model_id: str = field(default=DEFAULT_MODEL_ID)
    dimension: int = field(default=DEFAULT_DIMENSION)
    chunk_size: int = field(default=DEFAULT_CHUNK_SIZE)
    chunk_overlap: int = field(default=DEFAULT_CHUNK_OVERLAP)


class MarkdownToVectorPipelineParameters(PipelineParameters):
    graph_name: Annotated[
        str,
        Field(description="The RDF graph name that contains the document triples."),
    ] = "http://ontology.naas.ai/graph/document"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class MarkdownToVectorPipeline(Pipeline):
    """Reads Markdown files from the triple store, chunks them, embeds each chunk
    (with KV cache), and upserts vectors into the configured collection.

    Chunk RDF triples are inserted into the document graph so that the knowledge
    graph reflects what has been vectorized.
    """

    __configuration: MarkdownToVectorPipelineConfiguration
    module: ABIModule

    def __init__(self, configuration: MarkdownToVectorPipelineConfiguration) -> None:
        super().__init__(configuration)
        self.__configuration = configuration
        self.module = ABIModule.get_instance()

    # ------------------------------------------------------------------
    # Embedding cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        cfg = self.__configuration
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{cfg.model_id}_{cfg.dimension}_{text_hash}"

    def _get_cached_embedding(self, key: str) -> np.ndarray | None:
        try:
            kv = self.module.engine.services.kv
            raw = kv.get(key)
            vector = np.array(json.loads(raw.decode("utf-8")), dtype=np.float32)
            return vector
        except Exception:
            return None

    def _set_cached_embedding(self, key: str, vector: np.ndarray) -> None:
        try:
            kv = self.module.engine.services.kv
            raw = json.dumps(vector.tolist()).encode("utf-8")
            kv.set(key, raw)
        except Exception as exc:
            logger.warning("Failed to cache embedding for key %s: %s", key, exc)

    def _embed(self, texts: list[str], model: OpenAIEmbeddings) -> list[np.ndarray]:
        """Return embeddings for *texts*, using the KV cache when available."""
        results: list[np.ndarray | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        keys = [self._cache_key(t) for t in texts]

        for i, key in enumerate(keys):
            cached = self._get_cached_embedding(key)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            logger.info("Computing %d new embeddings …", len(uncached_texts))
            raw_vecs = model.embed_documents(uncached_texts)
            for pos, i in enumerate(uncached_indices):
                vec = np.array(raw_vecs[pos], dtype=np.float32)
                results[i] = vec
                self._set_cached_embedding(keys[i], vec)

        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _get_markdown_files(self, graph_name: str) -> list[dict]:
        """Return IRI + path for all Markdown files in the graph.

        If ``self.__configuration.file_path`` is set, only files whose
        ``doc:path`` contains that value are returned (containment semantics).
        """
        file_path_filter = self.__configuration.file_path.strip()
        filter_clause = (
            f'FILTER(CONTAINS(str(?path), "{file_path_filter}"))'
            if file_path_filter
            else ""
        )

        query = f"""
        PREFIX doc: <http://ontology.naas.ai/abi/document/>
        SELECT ?fileIRI ?path WHERE {{
            GRAPH <{graph_name}> {{
                ?fileIRI doc:mime_type "text/markdown" ;
                         doc:path ?path .
                {filter_clause}
            }}
        }}
        """
        results = self.module.engine.services.triple_store.query(query)
        rows = []
        for row in results:
            try:
                if hasattr(row, "fileIRI"):
                    iri = str(getattr(row, "fileIRI"))
                    path = str(getattr(row, "path"))
                else:
                    iri = str(row["fileIRI"])  # type: ignore[index]
                    path = str(row["path"])  # type: ignore[index]
                rows.append({"iri": iri, "path": path})
            except Exception:
                pass
        return rows

    def _chunk_already_vectorized(self, file_iri: str, graph_name: str) -> bool:
        """Return True if at least one chunk exists for this file in this collection."""
        query = f"""
        PREFIX doc: <http://ontology.naas.ai/abi/document/>
        SELECT ?chunk WHERE {{
            GRAPH <{graph_name}> {{
                ?chunk a <http://ontology.naas.ai/abi/document/Chunk> ;
                       doc:isChunkOf <{file_iri}> ;
                       doc:collection_name "{self.__configuration.collection_name}" .
            }}
        }}
        LIMIT 1
        """
        results = list(self.module.engine.services.triple_store.query(query))
        return len(results) > 0

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self, parameters: PipelineParameters) -> Graph:
        assert isinstance(parameters, MarkdownToVectorPipelineParameters)

        cfg = self.__configuration
        graph_name = parameters.graph_name

        logger.info(
            "MarkdownToVectorPipeline: collection=%s file_path_filter=%r",
            cfg.collection_name,
            cfg.file_path,
        )

        vector_store = self.module.engine.services.vector_store
        vector_store.ensure_collection(
            collection_name=cfg.collection_name,
            dimension=cfg.dimension,
            distance_metric="cosine",
        )

        embeddings_model = OpenAIEmbeddings(
            model=cfg.model_id, dimensions=cfg.dimension
        )

        markdown_files = self._get_markdown_files(graph_name)
        logger.info("Found %d Markdown file(s) to process.", len(markdown_files))

        combined_graph = Graph()

        for file_info in markdown_files:
            file_iri = file_info["iri"]
            file_path_val = file_info["path"]

            if self._chunk_already_vectorized(file_iri, graph_name):
                logger.debug(
                    "Skipping already-vectorized file: %s (collection=%s)",
                    file_path_val,
                    cfg.collection_name,
                )
                continue

            try:
                content_bytes = self.module.engine.services.object_storage.get_object(
                    prefix="", key=file_path_val
                )
                text = content_bytes.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.warning("Could not read %s: %s", file_path_val, exc)
                continue

            chunks = _split_markdown(text, cfg.chunk_size, cfg.chunk_overlap)
            if not chunks:
                logger.debug("No chunks produced for %s", file_path_val)
                continue

            logger.info(
                "Embedding %d chunk(s) for %s …", len(chunks), file_path_val
            )

            vectors = self._embed(chunks, embeddings_model)
            if len(vectors) != len(chunks):
                logger.error(
                    "Embedding count mismatch for %s: got %d, expected %d",
                    file_path_val,
                    len(vectors),
                    len(chunks),
                )
                continue

            ids: list[str] = []
            metadata_list: list[dict] = []
            payload_list: list[dict] = []

            for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                chunk_id = str(uuid.uuid4())
                ids.append(chunk_id)
                metadata_list.append(
                    {
                        "file_iri": file_iri,
                        "file_path": file_path_val,
                        "chunk_index": idx,
                        "collection_name": cfg.collection_name,
                    }
                )
                payload_list.append({"content": chunk_text})

                # Build RDF for this chunk
                chunk_entity = Chunk(
                    label=f"Chunk {idx} of {file_path_val}",
                    content=chunk_text,
                    chunk_index=idx,
                    embedding_id=chunk_id,
                    file_path=file_path_val,
                    collection_name=cfg.collection_name,
                    isChunkOf=[file_iri],
                )
                chunk_graph = chunk_entity.rdf()
                combined_graph += chunk_graph

                self.module.engine.services.triple_store.insert(
                    chunk_graph, graph_name=URIRef(graph_name)
                )

            vector_store.add_documents(
                collection_name=cfg.collection_name,
                ids=ids,
                vectors=vectors,
                metadata=metadata_list,
                payloads=payload_list,
            )

            logger.info(
                "Upserted %d vectors for %s into collection '%s'.",
                len(ids),
                file_path_val,
                cfg.collection_name,
            )

        return combined_graph

    # ------------------------------------------------------------------
    # Expose
    # ------------------------------------------------------------------

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="markdown_to_vector",
                description=(
                    "Chunk Markdown files from the document graph and store their "
                    "embeddings in the configured vector collection."
                ),
                func=lambda **kwargs: self.run(
                    MarkdownToVectorPipelineParameters(**kwargs)
                ),
                args_schema=MarkdownToVectorPipelineParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        return None

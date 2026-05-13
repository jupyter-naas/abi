"""Base pipeline that chunks files of a given mime type and stores embeddings
in a vector store.

Subclasses provide a mime type (via configuration) and implement
:meth:`ToVectorBasePipeline.chunk_content` to produce a list of
:class:`ChunkInfo` for each file. The base class handles file discovery in
the triple store, embedding (with KV cache), RDF chunk persistence, and
vector store upserts.

Cache key format: ``{model_id}_{dimension}_{sha256_hex(text.encode())}``
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any

import numpy as np
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import OpenAIEmbeddings
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import (
    Chunk,
)
from pydantic import Field, SecretStr
from rdflib import Graph, URIRef

DEFAULT_COLLECTION = "documents"
DEFAULT_MODEL_ID = "text-embedding-3-small"
DEFAULT_DIMENSION = 1536
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


@dataclass
class ChunkInfo:
    """A single chunk produced by a subclass.

    ``text`` is what gets embedded and stored as the chunk content.
    ``extra_metadata`` is attached to the vector store payload alongside the
    standard metadata (file_iri, file_path, chunk_index, collection_name) and
    can carry any subclass-specific fields (e.g. ``page_number`` for HTML).
    """

    text: str
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToVectorBasePipelineConfiguration(PipelineConfiguration):
    """Static configuration shared by all ``*ToVector`` pipelines."""

    api_key: str = field(default="")
    mime_type: str = field(default="")
    collection_name: str = field(default=DEFAULT_COLLECTION)
    file_path: str = field(default="")
    model_id: str = field(default=DEFAULT_MODEL_ID)
    dimension: int = field(default=DEFAULT_DIMENSION)
    chunk_size: int = field(default=DEFAULT_CHUNK_SIZE)
    chunk_overlap: int = field(default=DEFAULT_CHUNK_OVERLAP)


class ToVectorBasePipelineParameters(PipelineParameters):
    graph_name: Annotated[
        str,
        Field(description="The RDF graph name that contains the document triples."),
    ] = "http://ontology.naas.ai/graph/document"


class ToVectorBasePipeline(Pipeline):
    """Reads files of ``configuration.mime_type`` from the triple store, chunks
    each via the subclass-provided :meth:`chunk_content`, embeds the chunks
    (with KV cache), and upserts vectors into the configured collection.

    Chunk RDF triples are also inserted into the document graph.
    """

    _configuration: ToVectorBasePipelineConfiguration
    module: ABIModule

    def __init__(self, configuration: ToVectorBasePipelineConfiguration) -> None:
        super().__init__(configuration)
        self._configuration = configuration
        self.module = ABIModule.get_instance()

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    def chunk_content(self, content: bytes, file_path: str) -> list[ChunkInfo]:
        """Produce the chunks for a single file.

        ``content`` is the raw bytes pulled from object storage, ``file_path``
        the path of the file (useful for logging / debugging).
        """
        raise NotImplementedError("Subclasses must implement chunk_content")

    # ------------------------------------------------------------------
    # Embedding cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        cfg = self._configuration
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
        """Return embeddings for ``texts``, using the KV cache when available."""
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

    def _get_files_to_process(self, graph_name: str) -> list[dict]:
        """Return IRI + path for all files of the configured mime type.

        If ``self._configuration.file_path`` is set, only files whose
        ``doc:path`` contains that substring are returned.
        """
        cfg = self._configuration
        file_path_filter = cfg.file_path.strip()
        filter_clause = (
            f'FILTER(CONTAINS(str(?path), "{file_path_filter}"))'
            if file_path_filter
            else ""
        )

        query = f"""
        PREFIX doc: <http://ontology.naas.ai/abi/document/>
        SELECT ?fileIRI ?path WHERE {{
            GRAPH <{graph_name}> {{
                ?fileIRI doc:mime_type "{cfg.mime_type}" ;
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
                       doc:collection_name "{self._configuration.collection_name}" .
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
        assert isinstance(parameters, ToVectorBasePipelineParameters)

        cfg = self._configuration
        graph_name = parameters.graph_name

        logger.info(
            f"{type(self).__name__}: collection={cfg.collection_name} "
            f"mime_type={cfg.mime_type} file_path_filter={cfg.file_path}"
        )

        vector_store = self.module.engine.services.vector_store
        vector_store.ensure_collection(
            collection_name=cfg.collection_name,
            dimension=cfg.dimension,
            distance_metric="cosine",
        )

        embeddings_model = OpenAIEmbeddings(
            model=cfg.model_id, dimensions=cfg.dimension, api_key=SecretStr(cfg.api_key)
        )

        files = self._get_files_to_process(graph_name)
        logger.info(f"Found {len(files)} file(s) of mime type '{cfg.mime_type}'.")

        combined_graph = Graph()

        for file_info in files:
            file_iri = file_info["iri"]
            file_path_val = file_info["path"]

            if self._chunk_already_vectorized(file_iri, graph_name):
                logger.debug(
                    f"Skipping already-vectorized file: {file_path_val} "
                    f"(collection={cfg.collection_name})"
                )
                continue

            try:
                content_bytes = self.module.engine.services.object_storage.get_object(
                    prefix="", key=file_path_val
                )
            except Exception as exc:
                logger.warning(f"Could not read {file_path_val}: {exc}")
                continue

            try:
                chunk_infos = self.chunk_content(content_bytes, file_path_val)
            except Exception as exc:
                logger.warning(f"Chunking failed for {file_path_val}: {exc}")
                continue

            if not chunk_infos:
                logger.debug(f"No chunks produced for {file_path_val}")
                continue

            chunk_texts = [ci.text for ci in chunk_infos]
            logger.info(f"Embedding {len(chunk_texts)} chunk(s) for {file_path_val} …")

            vectors = self._embed(chunk_texts, embeddings_model)
            if len(vectors) != len(chunk_texts):
                logger.error(
                    f"Embedding count mismatch for {file_path_val}: "
                    f"got {len(vectors)}, expected {len(chunk_texts)}"
                )
                continue

            ids: list[str] = []
            metadata_list: list[dict] = []
            payload_list: list[dict] = []

            for idx, (chunk_info, vector) in enumerate(zip(chunk_infos, vectors)):
                chunk_id = str(uuid.uuid4())
                ids.append(chunk_id)

                metadata: dict[str, Any] = {
                    "file_iri": file_iri,
                    "file_path": file_path_val,
                    "chunk_index": idx,
                    "collection_name": cfg.collection_name,
                }
                metadata.update(chunk_info.extra_metadata)
                metadata_list.append(metadata)

                payload_list.append({"content": chunk_info.text})

                # Build RDF for this chunk
                chunk_entity = Chunk(
                    label=f"Chunk {idx} of {file_path_val}",
                    content=chunk_info.text,
                    chunk_index=idx,
                    embedding_id=chunk_id,
                    chunk_file_path=file_path_val,
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
                name=type(self).__name__,
                description=(
                    f"Chunk files of mime type '{self._configuration.mime_type}' "
                    "from the document graph and store their embeddings in the "
                    "configured vector collection."
                ),
                func=lambda **kwargs: self.run(
                    ToVectorBasePipelineParameters(**kwargs)
                ),
                args_schema=ToVectorBasePipelineParameters,
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

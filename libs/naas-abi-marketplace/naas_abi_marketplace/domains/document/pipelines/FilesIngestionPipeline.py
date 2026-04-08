"""Ingest local files from a directory into the document knowledge graph."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Any

from langchain_core.tools import BaseTool
from naas_abi_core import logger
from naas_abi_core.pipeline.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import (
    File,
)
from pydantic import Field
from rdflib import Graph, URIRef


@dataclass
class FilesIngestionPipelineConfiguration(PipelineConfiguration):
    """Configuration for ingesting a local directory of files."""

    triple_store: TripleStoreService
    object_storage: ObjectStorageService
    graph_name: URIRef


class FilesIngestionPipelineParameters(PipelineParameters):
    input_dir: Annotated[
        str,
        Field(
            description="Object storage prefix to ingest (recursive). Example: 'documents/my_folder'."
        ),
    ]
    output_dir: Annotated[
        str,
        Field(description="Directory to save the files to."),
    ]
    recursive: Annotated[
        bool,
        Field(description="Whether to ingest the directory recursively."),
    ] = True


class FilesIngestionPipeline(Pipeline):
    _triple_store: TripleStoreService
    _object_storage: ObjectStorageService
    _graph_name: URIRef

    def __init__(self, configuration: FilesIngestionPipelineConfiguration) -> None:
        super().__init__(configuration)
        self._triple_store = configuration.triple_store
        self._object_storage = configuration.object_storage
        self._graph_name = configuration.graph_name

        if self._graph_name not in self._triple_store.list_graphs():
            self._triple_store.create_graph(self._graph_name)
            logger.debug("Document graph created: %s", self._graph_name)

    def _parse_dt(self, value: Any) -> dt.datetime | None:
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = dt.datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                return parsed
            except ValueError:
                return None
        return None

    @staticmethod
    def _normalize_object_prefix(prefix: str) -> str:
        return prefix.strip().replace("\\", "/").strip("/")

    def _get_files_from_path(self, input_dir: str, *, recursive: bool) -> list[str]:
        """
        Return all file object keys under `input_dir`.

        Prefixes are object-storage keys, not local paths: ``Path(...).is_dir()`` is
        wrong here. S3-style listings use trailing ``/`` for common prefixes; for
        adapters that don't include that suffix, we probe by attempting to list the
        entry as a prefix.
        """
        root = self._normalize_object_prefix(input_dir)
        visited: set[str] = set()
        stack: list[str] = [root] if root else [""]
        files: list[str] = []

        while stack:
            prefix = stack.pop()
            if prefix in visited:
                continue
            visited.add(prefix)

            try:
                entries = self._object_storage.list_objects(prefix=prefix)
            except Exception as e:
                logger.warning(
                    "Object storage list_objects failed for %s: %s", prefix, e
                )
                continue

            for entry in entries:
                logger.debug("Processing entry: %s", entry)
                if not isinstance(entry, str) or not entry:
                    continue

                entry_norm = PurePosixPath(entry.replace("\\", "/")).as_posix()
                if entry_norm.endswith("/"):
                    child_prefix = entry_norm.rstrip("/")
                    if recursive and child_prefix:
                        stack.append(child_prefix)
                    continue

                if recursive:
                    # Some adapters don't include trailing "/" for directory keys.
                    # Try listing the entry as a prefix: if it succeeds, treat it as a directory.
                    try:
                        self._object_storage.list_objects(prefix=entry_norm)
                    except Exception:
                        pass
                    else:
                        stack.append(entry_norm)
                        continue

                if Path(entry_norm).name == "":
                    continue

                files.append(entry_norm)

        return files

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, FilesIngestionPipelineParameters):
            raise ValueError("Parameters must be FilesIngestionPipelineParameters")

        # Setup output dir
        output_dir_files = os.path.join(parameters.output_dir, "files")
        output_dir_sha256 = os.path.join(parameters.output_dir, "sha256")

        # Get files from input directory
        object_keys = self._get_files_from_path(
            parameters.input_dir, recursive=parameters.recursive
        )
        logger.info(f"Found {len(object_keys)} files in {parameters.input_dir}")

        # Process files
        g = Graph()
        ingested = 0
        for object_key in object_keys:
            print(object_key)
            file_name = Path(object_key).name
            file_path = object_key
            mime_type = None
            file_size_bytes = None
            created_time = None
            modified_time = None
            accessed_time = None
            permissions = None
            encoding = None

            try:
                meta = self._object_storage.get_object_metadata(
                    prefix="", key=object_key
                )
                mime_type = meta.mime_type
                file_size_bytes = meta.file_size_bytes
                permissions = meta.permissions
                encoding = meta.encoding
                created_time = (
                    self._parse_dt(meta.created_time) if meta.created_time else None
                )
                modified_time = (
                    self._parse_dt(meta.modified_time) if meta.modified_time else None
                )
                accessed_time = (
                    self._parse_dt(meta.accessed_time) if meta.accessed_time else None
                )
                permissions = meta.permissions
                sha_256 = meta.sha256

            except Exception as e:
                logger.warning(
                    f"Skipping key with unreadable metadata {object_key}: {e}"
                )
                continue

            # Check if file already processed with sha256. If so, remove file from input directory
            try:
                self._object_storage.get_object(prefix=output_dir_sha256, key=sha_256)
                logger.warning(
                    f"File {file_name} already processed with sha256 {sha_256}. Removing file from input directory."
                )
                self._object_storage.delete_object(prefix="", key=object_key)
                continue
            except Exception as e:
                logger.warning(
                    f"File {file_name} not processed with sha256 {sha_256}: {e}"
                )

            # Add file to graph
            logger.info(f"Adding file {file_name} to graph {self._graph_name}")
            file = File(
                label=file_name,
                file_path=file_path,
                file_name=file_name,
                file_size_bytes=file_size_bytes,
                created_time=created_time,
                modified_time=modified_time,
                accessed_time=accessed_time,
                sha256=sha_256,
                mime_type=mime_type,
                encoding=encoding,
                permissions=permissions,
            )

            g += file.rdf()
            ingested += 1

            # Remove file from input directory + Add it to output directory
            self._object_storage.put_object(
                prefix=output_dir_sha256,
                key=sha_256,
                content=self._object_storage.get_object(prefix="", key=object_key),
            )
            self._object_storage.put_object(
                prefix=output_dir_files,
                key=f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{file_name}",
                content=self._object_storage.get_object(prefix="", key=object_key),
            )
            self._object_storage.delete_object(prefix="", key=object_key)

        # Insert instances to graph
        if len(g) > 0:
            self._triple_store.insert(g, graph_name=self._graph_name)

        logger.info(
            f"AddFileFromDirPipeline ingested {ingested} files ({len(g)} triples) into {self._graph_name}",
        )
        return g

    def as_api(self):
        pass

    def as_tools(self) -> list[BaseTool]:
        return []


if __name__ == "__main__":
    """
    Command:
    uv run python libs/naas-abi-marketplace/naas_abi_marketplace/domains/document/pipelines/AddFileFromDirPipeline.py
    """
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.domains.document"])
    object_storage = engine.services.object_storage
    triple_store = engine.services.triple_store

    input_dir = "document"
    output_dir = "document_processed"
    graph_name = URIRef("http://ontology.naas.ai/graph/document")

    pipeline = FilesIngestionPipeline(
        FilesIngestionPipelineConfiguration(
            object_storage=object_storage,
            triple_store=triple_store,
            graph_name=graph_name,
        )
    )
    result_graph = pipeline.run(
        FilesIngestionPipelineParameters(input_dir=input_dir, output_dir=output_dir)
    )
    print(result_graph.serialize(format="turtle"))

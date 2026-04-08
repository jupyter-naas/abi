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
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import (
    File,
)
from pydantic import Field
from rdflib import Graph, URIRef
from naas_abi_marketplace.domains.document import ABIModule
import hashlib
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_marketplace.domains.document.pipelines.common import file_already_ingested

@dataclass
class FilesIngestionPipelineConfiguration(PipelineConfiguration):
    """Configuration for ingesting a local directory of files."""
    pass



class FilesIngestionPipelineParameters(PipelineParameters):
    input_path: Annotated[
        str,
        Field(
            description="Object storage prefix to ingest (recursive). Example: 'documents/my_folder'."
        ),
    ]
    output_path: Annotated[
        str,
        Field(description="Directory to save the files to."),
    ]
    graph_name: Annotated[
        str,
        Field(description="The graph name to ingest the files to."),
    ] = "http://ontology.naas.ai/graph/document"
    recursive: Annotated[
        bool,
        Field(description="Whether to ingest the directory recursively."),
    ] = True


class FilesIngestionPipeline(Pipeline):
    module: ABIModule

    def __init__(self, configuration: FilesIngestionPipelineConfiguration) -> None:
        super().__init__(configuration)
        self.module = ABIModule.get_instance()

    def __ensure_graph_exists(self, graph_name: str):
        if graph_name not in [str(graph) for graph in self.module.engine.services.triple_store.list_graphs()]:
            self.module.engine.services.triple_store.create_graph(URIRef(graph_name))
            logger.debug("Document graph created: %s", graph_name)

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

    def _get_files_from_path(self, input_path: str, *, recursive: bool) -> list[str]:
        """
        Return all file object keys under `input_path`.

        Prefixes are object-storage keys, not local paths: ``Path(...).is_dir()`` is
        wrong here. S3-style listings use trailing ``/`` for common prefixes; for
        adapters that don't include that suffix, we probe by attempting to list the
        entry as a prefix.
        """
        root = self._normalize_object_prefix(input_path)
        visited: set[str] = set()
        stack: list[str] = [root] if root else [""]
        files: list[str] = []

        while stack:
            prefix = stack.pop()
            if prefix in visited:
                continue
            visited.add(prefix)

            try:
                entries = self.module.engine.services.object_storage.list_objects(prefix=prefix)
            except Exceptions.ObjectNotFound:
                logger.warning(f"Object storage list_objects failed for {prefix}: Object not found")
                continue
            except Exception as e:
                logger.warning(
                    f"Object storage list_objects failed for {prefix}: {e}"
                )
                import traceback
                logger.warning(traceback.format_exc())
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
                        self.module.engine.services.object_storage.list_objects(prefix=entry_norm)
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

        # Get files from input directory
        object_keys = self._get_files_from_path(
            parameters.input_path, recursive=parameters.recursive
        )
        logger.info(f"Found {len(object_keys)} files in {parameters.input_path}")

        # Process files
        g = Graph()
        ingested = 0
        for object_key in object_keys:
            # First we need to compute the sha256 of the file to be able to check if it has already been ingested.
            sha_256 = hashlib.sha256(self.module.engine.services.object_storage.get_object(prefix="", key=object_key)).hexdigest()

            if file_already_ingested(sha_256, parameters.graph_name):
                logger.warning(
                    f"File {object_key} already processed with sha256 {sha_256}. Skipping file."
                )
                
                # We remove the file from the input directory to avoid processing it again.
                # TODO: Should we move it to a specific directory?
                self.module.engine.services.object_storage.delete_object(prefix="", key=object_key)
                continue



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
                meta = self.module.engine.services.object_storage.get_object_metadata(
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

            except Exception as e:
                logger.warning(
                    f"Skipping key with unreadable metadata {object_key}: {e}"
                )
                continue

            # Add file to graph
            logger.info(f"Adding file {file_name} to graph {parameters.graph_name}")
            
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

            # Move the file to the output directory.
            self.module.engine.services.object_storage.put_object(
                prefix=parameters.output_path,
                # Handle files with or without an extension robustly
                key=f"{file_name}_{datetime.now().strftime('%Y%m%dT%H%M%S')}" +
                    (f"_{file_name.split('.')[-1]}" if '.' in file_name else ""),
         
                content=self.module.engine.services.object_storage.get_object(prefix="", key=object_key),
            )
            self.module.engine.services.object_storage.delete_object(prefix="", key=object_key)

        # Insert instances to graph
        if len(g) > 0:
            self.__ensure_graph_exists(parameters.graph_name)
            self.module.engine.services.triple_store.insert(g, graph_name=parameters.graph_name)

        logger.info(
            f"AddFileFromDirPipeline ingested {ingested} files ({len(g)} triples) into {parameters.graph_name}",
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

    input_path = "file_ingestion/input"
    output_path = "file_ingestion/output"
    graph_name = URIRef("http://ontology.naas.ai/graph/document")

    pipeline = FilesIngestionPipeline(
        FilesIngestionPipelineConfiguration()
    )
    result_graph = pipeline.run(
        FilesIngestionPipelineParameters(input_path=input_path, output_path=output_path, graph_name=graph_name)
    )
    print(result_graph.serialize(format="turtle"))

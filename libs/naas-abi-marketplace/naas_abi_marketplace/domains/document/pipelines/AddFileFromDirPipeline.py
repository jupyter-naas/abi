"""Ingest local files from a directory into the document knowledge graph."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
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
class AddFileFromDirPipelineConfiguration(PipelineConfiguration):
    """Configuration for ingesting a local directory of files."""

    triple_store: TripleStoreService
    object_storage: ObjectStorageService
    graph_name: URIRef


class AddFileFromDirPipelineParameters(PipelineParameters):
    folder_path: Annotated[
        str,
        Field(
            description="Object storage prefix to ingest (recursive). Example: 'documents/my_folder'."
        ),
    ]
    recursive: Annotated[
        bool,
        Field(description="Whether to ingest the directory recursively."),
    ] = True


class AddFileFromDirPipeline(Pipeline):
    _triple_store: TripleStoreService
    _object_storage: ObjectStorageService
    _graph_name: URIRef

    def __init__(self, configuration: AddFileFromDirPipelineConfiguration) -> None:
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

    def _get_files_from_path(self, folder_path: str, *, recursive: bool) -> list[str]:
        """
        Return all file object keys under `folder_path`.

        Prefixes are object-storage keys, not local paths: ``Path(...).is_dir()`` is
        wrong here. S3-style listings use trailing ``/`` for common prefixes; for
        adapters that don't include that suffix, we probe by attempting to list the
        entry as a prefix.
        """
        root = self._normalize_object_prefix(folder_path)
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
        if not isinstance(parameters, AddFileFromDirPipelineParameters):
            raise ValueError("Parameters must be AddFileFromDirPipelineParameters")

        g = Graph()
        ingested = 0
        object_keys = self._get_files_from_path(
            parameters.folder_path, recursive=parameters.recursive
        )
        logger.info(f"Found {len(object_keys)} files in {parameters.folder_path}")
        for object_key in object_keys:
            file_name = Path(object_key).name
            file_path = object_key
            mime_type = None
            file_size_bytes = None
            created_time = None
            modified_time = None
            accessed_time = None
            is_file = True
            is_directory = False
            permissions = None
            encoding = None

            try:
                meta = self._object_storage.get_object_metadata(
                    prefix="", key=object_key
                )
                mime_type = meta.get("mime_type") or None
                file_size_bytes = int(meta.get("file_size_bytes") or 0)
                created_time = self._parse_dt(meta.get("created_time"))
                modified_time = self._parse_dt(meta.get("modified_time"))
                accessed_time = self._parse_dt(meta.get("accessed_time"))
                is_file = bool(meta.get("is_file", True))
                is_directory = bool(meta.get("is_directory", False))
                permissions = meta.get("permissions") or "unknown"
                encoding = meta.get("encoding") or "unknown"

            except Exception as e:
                logger.warning(
                    f"Skipping key with unreadable metadata {object_key}: {e}"
                )
                continue

            logger.info(f"Adding file {file_name} to graph {self._graph_name}")

            file = File(
                label=file_name,
                file_path=file_path,
                file_name=file_name,
                file_size_bytes=file_size_bytes,
                created_time=created_time,
                modified_time=modified_time,
                accessed_time=accessed_time,
                is_file=is_file,
                is_directory=is_directory,
            )
            if mime_type:
                file.mime_type = mime_type
            if permissions:
                file.permissions = permissions
            if encoding:
                file.encoding = encoding

            g += file.rdf()
            ingested += 1

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

    folder_path = "sec_gov"
    graph_name = URIRef("http://ontology.naas.ai/graph/document")

    pipeline = AddFileFromDirPipeline(
        AddFileFromDirPipelineConfiguration(
            object_storage=object_storage,
            triple_store=triple_store,
            graph_name=graph_name,
        )
    )
    result_graph = pipeline.run(
        AddFileFromDirPipelineParameters(folder_path=folder_path)
    )
    print(result_graph.serialize(format="turtle"))

"""Ingest local files from a directory into the document knowledge graph."""

from __future__ import annotations

import datetime as dt
import hashlib
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
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import (
    File,
)
from naas_abi_marketplace.domains.document.pipelines.common import file_already_ingested
from pydantic import Field
from rdflib import Graph, URIRef


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
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ] = "http://ontology.naas.ai/abi/document/FileIngestionProcessor"
    delete_from_input: Annotated[
        bool,
        Field(
            description="Whether to delete the files from the input directory after ingestion."
        ),
    ] = False


class FilesIngestionPipeline(Pipeline):
    module: ABIModule

    def __init__(self, configuration: FilesIngestionPipelineConfiguration) -> None:
        super().__init__(configuration)
        self.module = ABIModule.get_instance()

    def __ensure_graph_exists(self, graph_name: str):
        if graph_name not in [
            str(graph)
            for graph in self.module.engine.services.triple_store.list_graphs()
        ]:
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

    @classmethod
    def _build_destination_path(
        cls, input_path: str, output_path: str, object_key: str
    ) -> str:
        input_prefix = cls._normalize_object_prefix(input_path)
        output_prefix = cls._normalize_object_prefix(output_path)
        key_norm = cls._normalize_object_prefix(object_key)

        if input_prefix and key_norm.startswith(f"{input_prefix}/"):
            relative_key = key_norm[len(input_prefix) + 1 :]
        elif input_prefix and key_norm == input_prefix:
            relative_key = ""
        else:
            relative_key = key_norm

        relative_dir = (
            PurePosixPath(relative_key).parent.as_posix() if relative_key else ""
        )
        if relative_dir == ".":
            relative_dir = ""

        if not output_prefix:
            return relative_dir

        if not relative_dir:
            return output_prefix

        return PurePosixPath(output_prefix, relative_dir).as_posix()

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
                entries = self.module.engine.services.object_storage.list_objects(
                    prefix=prefix
                )
            except Exceptions.ObjectNotFound:
                logger.warning(
                    f"Object storage list_objects failed for {prefix}: Object not found"
                )
                continue
            except Exception as e:
                logger.warning(f"Object storage list_objects failed for {prefix}: {e}")
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
                        self.module.engine.services.object_storage.list_objects(
                            prefix=entry_norm
                        )
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
            file_content = self.module.engine.services.object_storage.get_object(
                prefix="", key=object_key
            )
            sha_256 = hashlib.sha256(file_content).hexdigest()

            if file_already_ingested(sha_256, parameters.graph_name):
                logger.warning(
                    f"File {object_key} already processed with sha256 {sha_256}. Skipping file."
                )

                # Honor delete_from_input for already ingested files as well.
                if parameters.delete_from_input is True:
                    self.module.engine.services.object_storage.delete_object(
                        prefix="", key=object_key
                    )
                continue

            file_name = Path(object_key).name
            meta = self.module.engine.services.object_storage.get_object_metadata(
                prefix="", key=object_key
            )

            # Add file to graph
            logger.info(f"Adding file {file_name} to graph {parameters.graph_name}")

            output_path = self._build_destination_path(
                input_path=parameters.input_path,
                output_path=parameters.output_path,
                object_key=object_key,
            )

            file = File.UploadAndCreateFile(
                content=file_content,
                filename=file_name,
                graph_name=parameters.graph_name,
                destination_path=output_path,
                metadata=meta,
                kwargs={
                    "processedBy": [parameters.processor_iri],
                },
            )

            g += file.rdf()
            ingested += 1

            if parameters.delete_from_input is True:
                print(f"Deleting file {object_key} from input directory")
                self.module.engine.services.object_storage.delete_object(
                    prefix="", key=object_key
                )
            else:
                print("Not deleting file from input directory")

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

    pipeline = FilesIngestionPipeline(FilesIngestionPipelineConfiguration())
    result_graph = pipeline.run(
        FilesIngestionPipelineParameters(
            input_path=input_path, output_path=output_path, graph_name=graph_name
        )
    )
    print(result_graph.serialize(format="turtle"))

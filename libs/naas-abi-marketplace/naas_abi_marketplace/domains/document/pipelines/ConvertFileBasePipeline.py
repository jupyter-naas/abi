import os
from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.classes.ontology_naas_ai.abi.document.File import (
    File,
)
from naas_abi_marketplace.domains.document.pipelines.common import get_files_to_process
from pydantic import Field
from rdflib import Graph


@dataclass
class ConvertFileBasePipelineConfiguration(PipelineConfiguration):
    """Configuration for ConvertFileBasePipeline."""

    mime_type: Annotated[
        str,
        Field(description="The MIME type of the files to convert."),
    ]
    output_mime_type: Annotated[
        str,
        Field(description="The MIME type of the converted output files."),
    ]
    output_extension: Annotated[
        str,
        Field(description="The file extension (including dot) appended to converted files."),
    ]


class ConvertFileBasePipelineParameters(PipelineParameters):
    graph_name: Annotated[
        str,
        Field(description="The graph name to ingest the files to."),
    ] = "http://ontology.naas.ai/graph/document"
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ]


class ConvertFileBasePipeline(Pipeline):
    """Base pipeline for converting files from one format to another."""

    __configuration: ConvertFileBasePipelineConfiguration
    module: ABIModule

    def __init__(self, configuration: ConvertFileBasePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.module = ABIModule.get_instance()

    def convert(self, file: File) -> str:
        raise NotImplementedError("This method should be implemented by the subclass")

    def run(self, parameters: PipelineParameters) -> Graph:
        assert isinstance(parameters, ConvertFileBasePipelineParameters)

        files_to_process = get_files_to_process(
            parameters.graph_name,
            self.__configuration.mime_type,
            parameters.processor_iri,
        )

        graph = Graph()

        for file_iri in files_to_process:
            f: File = File.from_iri(
                file_iri,
                query_executor=self.module.engine.services.triple_store.query,
                graph_name=parameters.graph_name,
            )
            converted_content = self.convert(f)
            new_file = File.UploadAndCreateFile(
                content=converted_content.encode("utf-8"),
                filename=f.file_name + self.__configuration.output_extension,
                graph_name=parameters.graph_name,
                destination_path=os.path.join(os.path.dirname(f.file_path)),
                mime_type=self.__configuration.output_mime_type,
                kwargs={
                    "derivedFrom": [f._uri],
                    "processedBy": [parameters.processor_iri],
                },
            )

            existing = list(f.processedBy or [])
            if parameters.processor_iri not in [str(p) for p in existing]:
                existing.append(parameters.processor_iri)
            f.processedBy = existing
            self.module.engine.services.triple_store.insert(
                f.rdf(), graph_name=parameters.graph_name
            )

            graph += new_file.rdf()
            graph += f.rdf()

        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="ConvertFileBase",
                description="Description of what the pipeline does",
                func=lambda **kwargs: self.run(
                    ConvertFileBasePipelineParameters(**kwargs)
                ),
                args_schema=ConvertFileBasePipelineParameters,
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
        if tags is None:
            tags = []
        return None

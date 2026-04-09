import os
from dataclasses import dataclass
from enum import Enum
from typing import Annotated

# PyMuPDF is used to convert the PDF to markdown
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
class ConvertToMarkdownBasePipelineConfiguration(PipelineConfiguration):
    """Configuration for ConvertToMarkdownBasePipeline."""

    mime_type: Annotated[
        str,
        Field(description="The MIME type of the files to convert to markdown."),
    ]


class ConvertToMarkdownBasePipelineParameters(PipelineParameters):
    graph_name: Annotated[
        str,
        Field(description="The graph name to ingest the files to."),
    ] = "http://ontology.naas.ai/graph/document"
    processor_iri: Annotated[
        str,
        Field(description="The IRI of the file ingestion processor."),
    ]


class ConvertToMarkdownBasePipeline(Pipeline):
    """Pipeline for adding a named individual."""

    __configuration: ConvertToMarkdownBasePipelineConfiguration
    module: ABIModule

    def __init__(self, configuration: ConvertToMarkdownBasePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.module = ABIModule.get_instance()

    def convert_to_markdown(self, file: File) -> str:
        raise NotImplementedError("This method should be implemented by the subclass")

    def run(self, parameters: PipelineParameters) -> Graph:
        # Implement the pipeline logic here.
        assert isinstance(parameters, ConvertToMarkdownBasePipelineParameters)

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
            md_content = self.convert_to_markdown(f)
            new_file = File.UploadAndCreateFile(
                content=md_content.encode("utf-8"),
                filename=f.file_name + ".md",
                graph_name=parameters.graph_name,
                destination_path=os.path.join(os.path.dirname(f.file_path)),
                kwargs={
                    "derivedFrom": [f._uri],
                    "processedBy": [parameters.processor_iri],
                },
            )

            graph += new_file.rdf()

        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="ConvertToMarkdownBase",
                description="Description of what the pipeline does",
                func=lambda **kwargs: self.run(
                    ConvertToMarkdownBasePipelineParameters(**kwargs)
                ),
                args_schema=ConvertToMarkdownBasePipelineParameters,
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

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.pipeline import (Pipeline, PipelineConfiguration,
                                    PipelineParameters)
from naas_abi_core.utils.Expose import APIRouter
from pydantic import Field
from rdflib import DCTERMS, OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef


@dataclass
class {{pipeline_name_pascal}}PipelineConfiguration(PipelineConfiguration):
    """Configuration for {{pipeline_name_pascal}}Pipeline."""

    pass


class {{pipeline_name_pascal}}PipelineParameters(PipelineParameters):
    # example_parameter: Annotated[
    #     str,
    #     Field(
    #         description="Description of the example parameter",
    #         example="Example value",
    #     ),
    # ]
    pass


class {{pipeline_name_pascal}}Pipeline(Pipeline[{{pipeline_name_pascal}}PipelineParameters]):
    """Pipeline for adding a named individual."""

    __configuration: {{pipeline_name_pascal}}PipelineConfiguration

    def __init__(self, configuration: {{pipeline_name_pascal}}PipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: {{pipeline_name_pascal}}PipelineParameters) -> Graph:
        # Implement the pipeline logic here.
        pass

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="{{pipeline_name_pascal}}",
                description="Description of what the pipeline does",
                func=lambda **kwargs: self.run(
                    {{pipeline_name_pascal}}PipelineParameters(**kwargs)
                ),
                args_schema={{pipeline_name_pascal}}PipelineParameters,
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

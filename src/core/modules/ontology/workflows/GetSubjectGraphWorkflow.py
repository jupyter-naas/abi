from abi.workflow import Workflow, WorkflowConfiguration
from dataclasses import dataclass
from pydantic import Field
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from abi.utils.SPARQL import get_subject_graph
from typing import Annotated, Optional
from enum import Enum
from abi.utils.Graph import URI_REGEX

@dataclass
class GetSubjectGraphWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for SearchIndividual workflow."""
    pass

class GetSubjectGraphWorkflowParameters(WorkflowParameters):
    """Parameters for GetSubjectGraph workflow."""
    uri: Annotated[str, Field(
        ...,
        description="URI of the individual/instance to get the subject graph of.",
        example="http://ontology.naas.ai/abi/a25ef0cc-56cf-458a-88c0-fabccb69e9b7",
        pattern=URI_REGEX,
    )]
    depth: Annotated[Optional[int], Field(
        2,
        description="Depth of the subject graph to get. 1 means the individual and its direct properties, 2 means the individual and its direct properties and the properties of the properties, etc.",
        example=2,
    )] = 2


class GetSubjectGraphWorkflow(Workflow):
    """Workflow for getting the subject graph of an ontology individual."""

    __configuration: GetSubjectGraphWorkflowConfiguration

    def __init__(self, configuration: GetSubjectGraphWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def get_subject_graph(self, parameters: GetSubjectGraphWorkflowParameters) -> str: 
        graph = get_subject_graph(parameters.uri, parameters.depth)
        return graph.serialize(format="turtle")
    
    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="get_subject_graph",
                description="Get the data about a specific individual/instance from the triplestore.",
                func=lambda **kwargs: self.get_subject_graph(
                    GetSubjectGraphWorkflowParameters(
                        **kwargs
                    )
                ),
                args_schema=GetSubjectGraphWorkflowParameters,
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


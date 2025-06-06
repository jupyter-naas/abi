from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, Annotated
from rdflib import URIRef, Literal, Graph, XSD
from abi.utils.Graph import ABI, URI_REGEX
from enum import Enum   

@dataclass
class UpdatePersonPipelineConfiguration(PipelineConfiguration):
    """Configuration for UpdatePersonPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService


class UpdatePersonPipelineParameters(PipelineParameters):
    individual_uri: Annotated[str, Field(
        description="URI of the person.",
        pattern=URI_REGEX,
        example="https://www.commoncoreontologies.org/ont00001262/Florent_Ravenel"
    )]
    first_name: Annotated[Optional[str], Field(
        None,
        description="First name of the person."
    )]
    last_name: Annotated[Optional[str], Field(
        None,
        description="Last name of the person."
    )]
    date_of_birth: Annotated[Optional[str], Field(
        None,
        description="Date of birth of the person. It must be in the format 'YYYY-MM-DD' (e.g. '1990-01-01').",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )]
    linkedin_page_uri: Annotated[Optional[str], Field(
        None,
        description="LinkedIn Page URI of the person from class: http://ontology.naas.ai/abi/LinkedInProfilePage or http://ontology.naas.ai/abi/LinkedInCompanyPage or http://ontology.naas.ai/abi/LinkedInSchoolPage.",
        pattern=URI_REGEX
    )]
    skill_uri: Annotated[str, Field(
        None,
        description="Skill URI of the person from class: https://www.commoncoreontologies.org/ont00000089",
        pattern=URI_REGEX
    )]

class UpdatePersonPipeline(Pipeline):
    """Pipeline for updating a person in the ontology."""

    __configuration: UpdatePersonPipelineConfiguration

    def __init__(self, configuration: UpdatePersonPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdatePersonPipelineParameters):
            raise ValueError("Parameters must be of type UpdatePersonPipelineParameters")
        
        # Initialize graphs
        graph_insert = Graph()

        # Get subject URI & graph
        individual_uri = URIRef(parameters.individual_uri)
        graph = self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Update properties
        if parameters.linkedin_page_uri:
            check_linkedin_page = list(graph.triples((individual_uri, ABI.hasLinkedInPage, URIRef(parameters.linkedin_page_uri))))
            if len(check_linkedin_page) == 0:
                graph_insert.add((individual_uri, ABI.hasLinkedInPage, URIRef(parameters.linkedin_page_uri)))
        if parameters.skill_uri:
            check_skill = list(graph.triples((individual_uri, ABI.hasSkill, URIRef(parameters.skill_uri))))
            if len(check_skill) == 0:
                graph_insert.add((individual_uri, ABI.hasSkill, URIRef(parameters.skill_uri)))
        if parameters.first_name:
            check_first_name = list(graph.triples((individual_uri, ABI.first_name, Literal(parameters.first_name))))
            if len(check_first_name) == 0:
                graph_insert.add((individual_uri, ABI.first_name, Literal(parameters.first_name)))
        if parameters.last_name:
            check_last_name = list(graph.triples((individual_uri, ABI.last_name, Literal(parameters.last_name))))
            if len(check_last_name) == 0:
                graph_insert.add((individual_uri, ABI.last_name, Literal(parameters.last_name)))
        if parameters.date_of_birth:
            check_date_of_birth = list(graph.triples((individual_uri, ABI.date_of_birth, Literal(parameters.date_of_birth, datatype=XSD.date))))
            if len(check_date_of_birth) == 0:
                graph_insert.add((individual_uri, ABI.date_of_birth, Literal(parameters.date_of_birth, datatype=XSD.date)))

        # Save the graph
        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph
    
    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_person",
                description="Update a person in the ontology.",
                func=lambda **kwargs: self.run(UpdatePersonPipelineParameters(**kwargs)),
                args_schema=UpdatePersonPipelineParameters,
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
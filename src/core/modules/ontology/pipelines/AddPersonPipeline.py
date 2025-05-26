from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from rdflib import URIRef, Literal, Graph, XSD
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
    ABI,
    CCO,
    URI_REGEX,
)


@dataclass
class AddPersonPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddPersonPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration


class AddPersonPipelineParameters(PipelineParameters):
    name: Optional[str] = Field(
        None, 
        description="Person's name. It must have a first name and a last name (e.g. 'Florent  Ravenel') to be added in class: https://www.commoncoreontologies.org/ont00001262", 
        pattern=r'^[A-Za-z]+\s+[A-Za-z]+.+$',
        example="Florent Ravenel"
    )
    individual_uri: Optional[str] = Field(
        None, 
        description="URI of the person if already known.", 
        pattern=URI_REGEX,
        example="https://www.commoncoreontologies.org/ont00001262/Florent_Ravenel"
    )
    first_name: Optional[str] = Field(
        None, 
        description="First name of the person. It can be identified as the first word (before the space) of the person's name (e.g. 'Florent Ravenel' -> 'Florent')"
    )
    last_name: Optional[str] = Field(
        None, 
        description="Last name of the person. It can be identified as the last word (after the space) of the person's name (e.g. 'Florent Ravenel' -> 'Ravenel')"
    )
    date_of_birth: Optional[str] = Field(
        None, 
        description="Date of birth of the person. It must be in the format 'YYYY-MM-DD' (e.g. '1990-01-01').", 
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    linkedin_page_uri: Optional[str] = Field(
        None,
        description="LinkedIn Page URI of the person from class: http://ontology.naas.ai/abi/LinkedInProfilePage or http://ontology.naas.ai/abi/LinkedInCompanyPage or http://ontology.naas.ai/abi/LinkedInSchoolPage.", 
        pattern=URI_REGEX
    )
    skill_uri: Optional[List[str]] = Field(
        None, 
        description="Skill URI of the person from class: https://www.commoncoreontologies.org/ont00000089",
        pattern=URI_REGEX
    )

class AddPersonPipeline(Pipeline):
    """Pipeline for adding a new person to the ontology."""

    __configuration: AddPersonPipelineConfiguration

    def __init__(self, configuration: AddPersonPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: AddPersonPipelineParameters) -> str:
        # Initialize graphs
        graph_insert = Graph()
        graph_remove = Graph()
        linkedin_page_uri = None
        skill_uri = None
        if parameters.linkedin_page_uri:
            linkedin_page_uri = URIRef(parameters.linkedin_page_uri)
        if parameters.skill_uri:
            skill_uri = [URIRef(uri) for uri in parameters.skill_uri]

        # Create person URI using first and last name
        if parameters.name and not parameters.individual_uri:
            individual_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
                class_uri=CCO.ont00001262,
                individual_label=parameters.name
            ))
            individual_uri = URIRef(individual_uri)
        else:
            graph = self.__configuration.triple_store.get_subject_graph(parameters.individual_uri)
            individual_uri = URIRef(parameters.individual_uri)

        # Update existing objects
        first_name_exists = False
        last_name_exists = False
        date_of_birth_exists = False
        linkedin_page_uri_exists = False
        skill_uri_exist = False
        for s, p, o in graph:
            if str(p) == "http://www.w3.org/2000/01/rdf-schema#label":
                if parameters.name is not None and str(o) != parameters.name:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.name)))
            if str(p) == "http://ontology.naas.ai/abi/first_name":
                first_name_exists = True
                if parameters.first_name is not None and str(o) != parameters.first_name:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.first_name)))
            if str(p) == "http://ontology.naas.ai/abi/last_name":
                last_name_exists = True
                if parameters.last_name is not None and str(o) != parameters.last_name:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.last_name)))
            if str(p) == "http://ontology.naas.ai/abi/date_of_birth":
                date_of_birth_exists = True
                if parameters.date_of_birth is not None and str(o) != parameters.date_of_birth:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.date_of_birth, datatype=XSD.date)))
            if str(p) == "http://ontology.naas.ai/abi/hasLinkedInPage":
                linkedin_page_uri_exists = True
                if linkedin_page_uri is not None and str(o) != linkedin_page_uri:
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, ABI.isLinkedInPageOf, s))  
                    graph_insert.add((s, p, linkedin_page_uri))
                    graph_insert.add((linkedin_page_uri, ABI.isLinkedInPageOf, s))
            if str(p) == "http://ontology.naas.ai/abi/hasSkill":
                skill_uri_exist = True
                if skill_uri is not None and str(o) != skill_uri:
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, ABI.isSkillOf, s))
                    graph_insert.add((s, p, skill_uri))
                    graph_insert.add((skill_uri, ABI.isSkillOf, s))

        # Add new objects
        if parameters.first_name and not first_name_exists:
            graph_insert.add((individual_uri, ABI.first_name, Literal(parameters.first_name)))
        if parameters.last_name and not last_name_exists:
            graph_insert.add((individual_uri, ABI.last_name, Literal(parameters.last_name)))
        if parameters.date_of_birth and not date_of_birth_exists:
            graph_insert.add((individual_uri, ABI.date_of_birth, Literal(parameters.date_of_birth, datatype=XSD.date))) 
        if linkedin_page_uri and not linkedin_page_uri_exists:   
            graph_insert.add((individual_uri, ABI.hasLinkedInPage, linkedin_page_uri))
            graph_insert.add((linkedin_page_uri, ABI.isLinkedInPageOf, individual_uri))
        if skill_uri and not skill_uri_exist:
            graph_insert.add((individual_uri, ABI.hasSkill, skill_uri))
            graph_insert.add((skill_uri, ABI.isSkillOf, individual_uri))

        # Save the graph
        self.__configuration.triple_store.insert(graph_insert)
        self.__configuration.triple_store.remove(graph_remove)
        graph += graph_insert
        return graph
    
    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="ontology_add_person",
                description="Add a person with a name to the ontology. A first name or last name alone is not enough to use this tool. It must have both first name and last name.",
                func=lambda **kwargs: self.run(AddPersonPipelineParameters(**kwargs)),
                args_schema=AddPersonPipelineParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass

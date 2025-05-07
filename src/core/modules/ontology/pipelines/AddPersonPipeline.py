from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from abi.utils.Graph import CCO, ABI
from rdflib import URIRef, Literal, RDF, OWL, Graph, XSD
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
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
        description="Person's name. It must have a first name and a last name (e.g. 'Florent Ravenel') to be added in class: https://www.commoncoreontologies.org/ont00001262",
    )
    individual_uri: Optional[str] = Field(
        None,
        description="URI of the person if already known. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    first_name: Optional[str] = Field(
        None,
        description="First name of the person. It can be identified as the first word (before the space) of the person's name (e.g. 'Florent Ravenel' -> 'Florent')",
    )
    last_name: Optional[str] = Field(
        None,
        description="Last name of the person. It can be identified as the last word (after the space) of the person's name (e.g. 'Florent Ravenel' -> 'Ravenel')",
    )
    date_of_birth: Optional[str] = Field(
        None,
        description="Date of birth of the person. It must be in the format 'YYYY-MM-DD' (e.g. '1990-01-01').",
    )
    linkedin_page_uri: Optional[str] = Field(
        None,
        description="LinkedIn Page URI from class: http://ontology.naas.ai/abi/LinkedInProfilePage or http://ontology.naas.ai/abi/LinkedInCompanyPage or http://ontology.naas.ai/abi/LinkedInSchoolPage. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    skill_uris: Optional[List[str]] = Field(
        None,
        description="List of skills URIs from class: https://www.commoncoreontologies.org/ont00000089. URIs must start with 'http://ontology.naas.ai/abi/'.",
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
        # Initialize a new graph
        graph = Graph()

        # Create person URI using first and last name
        person_uri = parameters.individual_uri
        if parameters.name and not person_uri:
            person_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=CCO.ont00001262, individual_label=parameters.name
                )
            )
        else:
            if person_uri.startswith("http://ontology.naas.ai/abi/"):
                person_uri = URIRef(person_uri)
            else:
                raise ValueError(
                    f"Invalid Person URI: {person_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add person type and properties
        if parameters.first_name:
            graph.add((person_uri, ABI.first_name, Literal(parameters.first_name)))
        if parameters.last_name:
            graph.add((person_uri, ABI.last_name, Literal(parameters.last_name)))
        if parameters.date_of_birth:
            graph.add(
                (
                    person_uri,
                    ABI.date_of_birth,
                    Literal(parameters.date_of_birth, datatype=XSD.date),
                )
            )

        # Add LinkedIn page URI
        if parameters.linkedin_page_uri:
            if parameters.linkedin_page_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add(
                    (
                        person_uri,
                        ABI.hasLinkedInPage,
                        URIRef(parameters.linkedin_page_uri),
                    )
                )
                graph.add(
                    (
                        URIRef(parameters.linkedin_page_uri),
                        ABI.isLinkedInPageOf,
                        person_uri,
                    )
                )
            else:
                raise ValueError(
                    f"Invalid LinkedIn Page URI: {parameters.linkedin_page_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add skills URIs
        if parameters.skill_uris:
            for skill_uri in parameters.skill_uris:
                if skill_uri.startswith("http://ontology.naas.ai/abi/"):
                    graph.add((person_uri, ABI.hasSkill, URIRef(skill_uri)))
                    graph.add((URIRef(skill_uri), ABI.isSkillOf, person_uri))
                else:
                    raise ValueError(
                        f"Invalid Skill URI: {skill_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                    )

        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return person_uri

    def as_tools(self) -> list[StructuredTool]:
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

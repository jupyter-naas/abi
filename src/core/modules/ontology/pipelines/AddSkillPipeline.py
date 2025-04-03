from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from rdflib import Literal, Graph, URIRef
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
    CCO,
    DCTERMS
)

@dataclass
class AddSkillPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddSkillPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddSkillPipelineParameters(PipelineParameters):
    name: Optional[str] = Field(None, description="Name of the skill (e.g. 'Python Programming') to be added in class: https://www.commoncoreontologies.org/ont00000089")
    individual_uri: Optional[str] = Field(None, description="URI of the skill if already known. It must start with 'http://ontology.naas.ai/abi/'.")
    description: Optional[str] = Field(None, description="Description of the skill")
    person_uris: Optional[List[str]] = Field(None, description="List of person URIs from class: https://www.commoncoreontologies.org/ont00001262. URIs must start with 'http://ontology.naas.ai/abi/'.")

class AddSkillPipeline(Pipeline):
    """Pipeline for adding a new skill to the ontology."""
    __configuration: AddSkillPipelineConfiguration
    
    def __init__(self, configuration: AddSkillPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddSkillPipelineParameters) -> str:
        # Initialize a new graph
        graph = Graph()

        # Create skill URI using the name
        skill_uri = parameters.individual_uri
        if parameters.name and not skill_uri:
            skill_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
                class_uri=CCO.ont00000089,
                individual_label=parameters.name
            ))
        else:
            if skill_uri.startswith("http://ontology.naas.ai/abi/"):
                skill_uri = URIRef(skill_uri)
            else:
                raise ValueError(f"Invalid Skill URI: {skill_uri}. It must start with 'http://ontology.naas.ai/abi/'.")

        # Add skill properties
        if parameters.description:
            graph.add((skill_uri, DCTERMS.description, Literal(parameters.description)))

        # Add person URIs
        if parameters.person_uris:
            for person_uri in parameters.person_uris:
                if person_uri.startswith("http://ontology.naas.ai/abi/"):
                    graph.add((skill_uri, CCO.isSkillOf, URIRef(person_uri)))
                    graph.add((URIRef(person_uri), CCO.hasSkill, skill_uri))
                else:
                    raise ValueError(f"Invalid Person URI: {person_uri}. It must start with 'http://ontology.naas.ai/abi/'.")
        
        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return skill_uri
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_skill",
                description="Add a skill with a name and description to the ontology.",
                func=lambda **kwargs: self.run(AddSkillPipelineParameters(**kwargs)),
                args_schema=AddSkillPipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 
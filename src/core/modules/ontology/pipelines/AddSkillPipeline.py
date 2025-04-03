from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional
from rdflib import Literal, Graph, Namespace
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
    name: str = Field(..., description="Name of the skill (e.g. 'Python Programming')")
    description: Optional[str] = Field(None, description="Description of the skill")

class AddSkillPipeline(Pipeline):
    """Pipeline for adding a new skill to the ontology."""
    __configuration: AddSkillPipelineConfiguration
    
    def __init__(self, configuration: AddSkillPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddSkillPipelineParameters) -> str:
        # Create skill URI using the name
        skill_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
            class_uri=CCO.ont00000089,
            individual_label=parameters.name
        ))

        # Initialize a new graph for performance
        graph.bind("dcterms", DCTERMS)

        # Add skill properties
        if parameters.description:
            graph.add((skill_uri, DCTERMS.description, Literal(parameters.description)))
        
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
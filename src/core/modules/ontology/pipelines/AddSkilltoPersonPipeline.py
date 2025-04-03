from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, Any
from abi.utils.Graph import CCO, ABI, ABIGraph
from rdflib import Graph, URIRef, Literal, RDF, OWL, RDFS
from urllib.parse import quote

@dataclass
class AddSkilltoPersonPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddSkilltoPersonPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
    """
    triple_store: ITripleStoreService

class AddSkilltoPersonPipelineParameters(PipelineParameters):
    person_uri: str = Field(..., description="Person URI. It must be start with 'http://ontology.naas.ai/abi/'.")
    skill_uri: str = Field(..., description="Skill URI. It must be start with 'http://ontology.naas.ai/abi/'.")

class AddSkilltoPersonPipeline(Pipeline):
    """Pipeline for adding a skill to a person."""
    __configuration: AddSkilltoPersonPipelineConfiguration
    
    def __init__(self, configuration: AddSkilltoPersonPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: AddSkilltoPersonPipelineParameters) -> str:
        # Init URI
        person_uri = URIRef(str(parameters.person_uri))
        skill_uri = URIRef(str(parameters.skill_uri))
        
        # Init person graph
        graph = Graph()
        graph.add((person_uri, ABI.hasSkill, skill_uri))
        self.__configuration.triple_store.insert(graph)

        # Init skill graph
        graph = Graph()
        graph.add((skill_uri, ABI.isSkillOf, person_uri))
        self.__configuration.triple_store.insert(graph)
        return f"Skill {parameters.skill_uri} added to person {parameters.person_uri}"
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_skill_to_person",
                description="Adds a skill to a person. Search for the person URI (class: https://www.commoncoreontologies.org/ont00001262) and skill URI (class: https://www.commoncoreontologies.org/ont00000089) using the `ontology_search_individual` tool before calling this tool.",
                func=lambda person_uri, skill_uri: self.run(AddSkilltoPersonPipelineParameters(person_uri=person_uri, skill_uri=skill_uri)),
                args_schema=AddSkilltoPersonPipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
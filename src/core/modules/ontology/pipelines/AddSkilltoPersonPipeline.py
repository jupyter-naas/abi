from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
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
        ontology_store (IOntologyStoreService): The ontology store service to use
    """
    ontology_store: IOntologyStoreService

class AddSkilltoPersonPipelineParameters(PipelineParameters):
    person_uri: str = Field(..., description="Person URI. It must be start with 'http://ontology.naas.ai/abi/'.")
    skill_uri: str = Field(..., description="Skill URI. It must be start with 'http://ontology.naas.ai/abi/'.")

class AddSkilltoPersonPipeline(Pipeline):
    """Pipeline for adding a skill to a person."""
    __configuration: AddSkilltoPersonPipelineConfiguration
    
    def __init__(self, configuration: AddSkilltoPersonPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: AddSkilltoPersonPipelineParameters) -> Graph:
        # Init URI
        person_uri = URIRef(str(parameters.person_uri))
        skill_uri = URIRef(str(parameters.skill_uri))
        
        # Init person graph
        person_graph_name = "person_ont00001262"
        person_graph = ABIGraph()
        try:
            person_graph = self.__configuration.ontology_store.get(person_graph_name)
        except Exception as e:
            logger.info(f"Error getting person graph: {e}")

        person_graph.add((person_uri, ABI.hasSkill, skill_uri))
        self.__configuration.ontology_store.insert(person_graph_name, person_graph)

        # Init skill graph
        skill_graph_name = "skill_ont00000089"
        skill_graph = ABIGraph()
        try:
            skill_graph = self.__configuration.ontology_store.get(skill_graph_name)
        except Exception as e:
            logger.info(f"Error getting skill graph: {e}")

        skill_graph.add((skill_uri, ABI.isSkillOf, person_uri))
        self.__configuration.ontology_store.insert(skill_graph_name, skill_graph)
    
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
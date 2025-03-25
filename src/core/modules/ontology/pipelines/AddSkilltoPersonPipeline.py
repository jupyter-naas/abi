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
    person_name: str = Field(..., description="Person name")
    skill_name: str = Field(..., description="Skill name")

class AddSkilltoPersonPipeline(Pipeline):
    """Pipeline for adding a skill to a person."""
    __configuration: AddSkilltoPersonPipelineConfiguration
    
    def __init__(self, configuration: AddSkilltoPersonPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: AddSkilltoPersonPipelineParameters) -> Graph:
        # Init URI
        person_id = quote(parameters.person_name.lower(), safe=":/#")
        person_uri = ABI[person_id]
        skill_id = quote(parameters.skill_name.lower(), safe=":/#")
        skill_uri = ABI[skill_id]
        
        # Init person graph
        person_graph_name = "ont00001262_person"
        person_graph = ABIGraph()
        try:
            person_graph = self.__configuration.ontology_store.get(person_graph_name)
        except Exception as e:
            logger.info(f"Error getting person graph: {e}")

        person_graph.add((person_uri, RDF.type, OWL.NamedIndividual))
        person_graph.add((person_uri, RDF.type, CCO.ont00001262))
        person_graph.add((person_uri, RDFS.label, Literal(parameters.person_name)))
        person_graph.add((person_uri, ABI.hasSkill, skill_uri))
        self.__configuration.ontology_store.store(person_graph_name, person_graph)

        # Init skill graph
        skill_graph_name = "ont00000089_skill"
        skill_graph = ABIGraph()
        try:
            skill_graph = self.__configuration.ontology_store.get(skill_graph_name)
        except Exception as e:
            logger.info(f"Error getting skill graph: {e}")

        skill_graph.add((skill_uri, RDF.type, OWL.NamedIndividual))
        skill_graph.add((skill_uri, RDF.type, CCO.ont00000089)) 
        skill_graph.add((skill_uri, RDFS.label, Literal(parameters.skill_name)))
        skill_graph.add((skill_uri, ABI.isSkillOf, person_uri))
        self.__configuration.ontology_store.store(skill_graph_name, skill_graph)
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_skill_to_person",
                description="Adds a skill to a person",
                func=lambda person_name, skill_name: self.run(AddSkilltoPersonPipelineParameters(person_name=person_name, skill_name=skill_name)),
                args_schema=AddSkilltoPersonPipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
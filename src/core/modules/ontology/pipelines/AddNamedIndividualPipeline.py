from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService, OntologyEvent
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, Any
from abi.utils.Graph import ABIGraph, CCO
from rdflib import Graph

@dataclass
class AddNamedIndividualPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddNamedIndividualPipeline.
    
    Attributes:
        ontology_store (IOntologyStoreService): The ontology store service to use
    """
    ontology_store: IOntologyStoreService

class AddNamedIndividualPipelineParameters(PipelineParameters):
    class_uri: str = Field(..., description="Class URI")
    label: str = Field(..., description="Label")

class AddNamedIndividualPipeline(Pipeline):
    """Pipeline for adding a named individual."""
    __configuration: AddNamedIndividualPipelineConfiguration
    
    def __init__(self, configuration: AddNamedIndividualPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def add_named_individual(self, parameters: AddNamedIndividualPipelineParameters) -> Graph:
        
        # Init person graph
        person_graph_name = "cco:ont00001262_person"
        person_graph = self.init_abi_graph(person_graph_name)

        # Init skill graph
        skill_graph_name = "cco:ont00000089_skill"
        skill_graph = self.init_abi_graph(skill_graph_name)

        # Add person skill
        existing_graph = self.__configuration.ontology_store.get(graph_name)
        person_graph.self.add((uri, RDF.type, OWL.NamedIndividual))
            self.add((uri, RDF.type, URIRef(is_a)))
            self.add((uri, RDFS.label, Literal(str(label), lang=lang)))
        self.__configuration.ontology_store.store(person_graph_name, person_graph)
        
        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="add_skill_to_person",
                description="Adds a skill to a person",
                func=lambda **kwargs: self.add_skill_to_person(AddSkilltoPersonPipelineParameters(**kwargs)),
                args_schema=AddSkilltoPersonPipelineParameters
            )
        ]

    def as_api(self) -> None:
        pass
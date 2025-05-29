from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from src.core.modules.ontology.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflow,
    ConvertOntologyGraphToYamlConfiguration,
    ConvertOntologyGraphToYamlParameters,
)
from src import services
from dataclasses import dataclass
from pydantic import Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from typing import Any, Union
from abi.services.triple_store.TripleStorePorts import OntologyEvent
from rdflib import Graph, URIRef, RDFS, Literal
from abi.utils.SPARQL import get_class_uri_from_individual_uri
from abi.utils.Storage import save_triples
import os
from typing import Annotated
from enum import Enum

URI_REGEX = r"http:\/\/ontology\.naas\.ai\/abi\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

@dataclass
class CreateIndividualOntologyYamlConfiguration(WorkflowConfiguration):
    """Configuration for CreateOntologyYAML workflow.

    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """

    triple_store: ITripleStoreService
    convert_ontology_graph_config: ConvertOntologyGraphToYamlConfiguration
    data_store_path: str = "datastore/ontology"


class CreateIndividualOntologyYamlParameters(WorkflowParameters):
    """Parameters for CreateOntologyYAML workflow execution.

    Attributes:
        ontology_name (str): The name of the ontology store to use
        label (str): The label of the ontology
        description (str): The description of the ontology
        logo_url (str): The URL of the ontology logo
        level (str): The level of the ontology (e.g., 'TOP_LEVEL', 'MID_LEVEL', 'DOMAIN', 'USE_CASE')
        display_relations_names (bool): Whether to display relation names in the visualization
    """

    individual_uri: Annotated[str, Field(
        ..., 
        description="The URI of the individual to convert to YAML",
        pattern=URI_REGEX
    )]
    distance: Annotated[int, Field(
        default=2,
        description="The distance to the individual to convert to YAML"
    )]


class CreateIndividualOntologyYamlWorkflow(Workflow):
    """Workflow for converting ontology files to YAML and pushing them to a Naas workspace."""

    __configuration: CreateIndividualOntologyYamlConfiguration

    def __init__(self, configuration: CreateIndividualOntologyYamlConfiguration):
        self.__configuration = configuration
        self.__convert_ontology_graph_workflow = ConvertOntologyGraphToYamlWorkflow(
            self.__configuration.convert_ontology_graph_config
        )

    def trigger(self, event: OntologyEvent, triple: tuple[Any, Any, Any]) -> Union[str, None]:
        s, p, o = triple
        if str(event) != str(OntologyEvent.INSERT) or not str(s).startswith('http://ontology.naas.ai/abi/') or not str(o).startswith('http://ontology.naas.ai/abi/'):
            return None

        # Get class type from URI
        class_uri = get_class_uri_from_individual_uri(s)
        class_uri_triggers = [
            "https://www.commoncoreontologies.org/ont00001262",  # Person
            "https://www.commoncoreontologies.org/ont00000443",  # Commercial Organization
        ]
        if class_uri in class_uri_triggers:
            return self.graph_to_yaml(CreateIndividualOntologyYamlParameters(individual_uri=s, distance=2))
        return None
    
    def __add_object_graphs(self, graph: Graph, distance: int) -> Graph:
        """Add all related object graphs up to specified distance"""
        visited = set()
        to_visit = []
        
        # Get initial objects to visit from main graph
        for s, p, o in graph:
            if isinstance(o, URIRef) and str(o).startswith('http://ontology.naas.ai/abi/'):
                to_visit.append((str(o), 1))
                
        # Process objects level by level up to max distance
        while to_visit:
            uri, current_distance = to_visit.pop(0)
            
            if uri in visited or current_distance > distance:
                continue
                
            visited.add(uri)
            object_graph = self.__configuration.triple_store.get_subject_graph(uri)
            
            # Add all triples from this object's graph
            for s, p, o in object_graph:
                graph.add((s, p, o))
                # Queue new objects for next level if within distance
                if isinstance(o, URIRef) and str(o).startswith('http://ontology.naas.ai/abi/'):
                    to_visit.append((str(o), current_distance + 1))
        return graph
    
    def get_individual_graph(self, parameters: CreateIndividualOntologyYamlParameters) -> Graph:
        # Initialize graph
        graph = services.triple_store_service.get_subject_graph(parameters.individual_uri)

        # Add all related object graphs
        graph = self.__add_object_graphs(graph, parameters.distance)
        return graph
    
    def get_individual_graph_serialized(self, parameters: CreateIndividualOntologyYamlParameters) -> Union[str, None]:
        """Get the individual graph serialized as turtle format."""
        graph = self.get_individual_graph(parameters)
        return graph.serialize(format="turtle")

    def graph_to_yaml(self, parameters: CreateIndividualOntologyYamlParameters) -> Union[str, None]:
        # Create individual graph
        graph = self.get_individual_graph(parameters)

        # Get label from individual URI
        ontology_id = None
        ontology_label = "" 
        ontology_description = ""
        ontology_logo_url = ""
        new_ontology = True
        for s, p, o in graph:
            if p == RDFS.label and s == URIRef(parameters.individual_uri):
                ontology_label = str(o)
                ontology_description = f"{ontology_label} Ontology"
            if str(p) == "http://ontology.naas.ai/abi/logo":
                ontology_logo_url = str(o)
            if str(p) == "http://ontology.naas.ai/abi/naas_ontology_id":
                ontology_id = str(o)
                new_ontology = False

        # Save graph in turtle format
        save_triples(
            graph, 
            os.path.join(self.__configuration.data_store_path, "individual", f"{ontology_label}_{parameters.individual_uri.split('/')[-1]}"), 
            f"{ontology_label}_{parameters.individual_uri.split('/')[-1]}.ttl"
        )

        # Convert graph to YAML & push to Naas workspace
        ontology_id = self.__convert_ontology_graph_workflow.graph_to_yaml(ConvertOntologyGraphToYamlParameters(
            graph=graph.serialize(format="turtle"),
            ontology_id=ontology_id,
            label=ontology_label,
            description=ontology_description,
            logo_url=ontology_logo_url
        ))
        if new_ontology:
            graph_insert = Graph()
            graph_insert.add((URIRef(parameters.individual_uri), URIRef("http://ontology.naas.ai/abi/naas_ontology_id"), Literal(ontology_id)))
            self.__configuration.triple_store.insert(graph_insert)
        return ontology_id

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="get_individual_ontology",
                description="Get the ontology graph from an individual/instance in triple store.",
                func=lambda **kwargs: self.get_individual_graph_serialized(
                    CreateIndividualOntologyYamlParameters(**kwargs)
                ),
                args_schema=CreateIndividualOntologyYamlParameters,
            ),
            StructuredTool(
                name="create_individual_ontology_yaml",
                description="Create or Update a YAML ontology from an individual/instance in triple store and push it to Naas workspace.",
                func=lambda **kwargs: self.graph_to_yaml(
                    CreateIndividualOntologyYamlParameters(**kwargs)
                ),
                args_schema=CreateIndividualOntologyYamlParameters,
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


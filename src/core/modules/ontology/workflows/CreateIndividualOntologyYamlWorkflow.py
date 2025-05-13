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
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Any
from abi.services.triple_store.TripleStorePorts import OntologyEvent
import pydash as _
from rdflib import Graph, URIRef, RDFS
from abi.utils.SPARQL import get_class_uri_from_individual_uri


@dataclass
class CreateIndividualOntologyYamlConfiguration(WorkflowConfiguration):
    """Configuration for CreateOntologyYAML workflow.

    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """

    triple_store: ITripleStoreService
    convert_ontology_graph_config: ConvertOntologyGraphToYamlConfiguration


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

    individual_uri: str = Field(
        ..., description="The URI of the individual to convert to YAML"
    )
    distance: int = 2


class CreateIndividualOntologyYamlWorkflow(Workflow):
    """Workflow for converting ontology files to YAML and pushing them to a Naas workspace."""

    __configuration: CreateIndividualOntologyYamlConfiguration

    def __init__(self, configuration: CreateIndividualOntologyYamlConfiguration):
        self.__configuration = configuration
        self.__convert_ontology_graph_workflow = ConvertOntologyGraphToYamlWorkflow(
            self.__configuration.convert_ontology_graph_config
        )

    def trigger(self, event: OntologyEvent, triple: tuple[Any, Any, Any]) -> Graph:
        s, p, o = triple
        # logger.debug(f"==> Triggering Create Individual Ontology YAML Workflow: {s} {p} {o}")
        if (
            str(event) != str(OntologyEvent.INSERT)
            or not str(o).startswith("http")
            or str(o) == "http://www.w3.org/2002/07/owl#NamedIndividual"
        ):
            # logger.debug(f"==> Skipping individual ontology YAML creation for {s} {p} {o}")
            return None

        # Get class type from URI
        class_uri = get_class_uri_from_individual_uri(s)
        class_uri_triggers = [
            "https://www.commoncoreontologies.org/ont00001262",  # Person
            "https://www.commoncoreontologies.org/ont00000443",  # Commercial Organization
        ]
        if class_uri in class_uri_triggers:
            logger.debug(f"==> Creating individual ontology YAML for {s} {p} {o}")
            return self.graph_to_yaml(
                CreateIndividualOntologyYamlParameters(individual_uri=s)
            )
        return None

    def graph_to_yaml(self, parameters: CreateIndividualOntologyYamlParameters) -> str:
        # Initialize graph
        graph = services.triple_store_service.get_subject_graph(
            parameters.individual_uri
        )

        def add_object_graphs(graph: Graph, distance: int) -> Graph:
            """Add all related object graphs up to specified distance"""
            visited = set()
            to_visit = []

            # Get initial objects to visit from main graph
            for s, p, o in graph:
                if isinstance(o, URIRef) and str(o).startswith(
                    "http://ontology.naas.ai/abi/"
                ):
                    to_visit.append((str(o), 1))

            # Process objects level by level up to max distance
            while to_visit:
                uri, current_distance = to_visit.pop(0)

                if uri in visited or current_distance > distance:
                    continue

                visited.add(uri)
                object_graph = services.triple_store_service.get_subject_graph(uri)

                # Add all triples from this object's graph
                for s, p, o in object_graph:
                    graph.add((s, p, o))
                    # Queue new objects for next level if within distance
                    if isinstance(o, URIRef) and str(o).startswith(
                        "http://ontology.naas.ai/abi/"
                    ):
                        to_visit.append((str(o), current_distance + 1))
            return graph

        # Get label from individual URI
        ontology_label = None
        ontology_description = None
        for s, p, o in graph:
            if p == RDFS.label and s == URIRef(parameters.individual_uri):
                ontology_label = str(o)
                ontology_description = f"{ontology_label} Ontology"

        # Add all related object graphs
        graph = add_object_graphs(graph, parameters.distance)

        # Convert graph to YAML & push to Naas workspace
        ontology_id = self.__convert_ontology_graph_workflow.graph_to_yaml(
            ConvertOntologyGraphToYamlParameters(
                graph=graph.serialize(format="turtle"),
                label=ontology_label,
                description=ontology_description,
            )
        )
        return ontology_id

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="ontology_create_individual_yaml",
                description="Create an ontology individual YAML and push it to Naas workspace.",
                func=lambda **kwargs: self.graph_to_yaml(
                    CreateIndividualOntologyYamlParameters(**kwargs)
                ),
                args_schema=CreateIndividualOntologyYamlParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass

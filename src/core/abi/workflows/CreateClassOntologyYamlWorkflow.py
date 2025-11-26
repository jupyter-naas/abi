from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Union

from abi import logger
from abi.services.triple_store.TripleStorePorts import (
    ITripleStoreService,
    OntologyEvent,
)
from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field
from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

from src import services
from src.core.abi.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflow,
    ConvertOntologyGraphToYamlWorkflowConfiguration,
    ConvertOntologyGraphToYamlWorkflowParameters,
)
from src.utils.SPARQL import get_class_uri_from_individual_uri, results_to_list


@dataclass
class CreateClassOntologyYamlWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateOntologyYAML workflow.

    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """

    triple_store: ITripleStoreService
    convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration


class CreateClassOntologyYamlWorkflowParameters(WorkflowParameters):
    """Parameters for CreateOntologyYAML workflow execution.

    Attributes:
        ontology_name (str): The name of the ontology store to use
        label (str): The label of the ontology
        description (str): The description of the ontology
        logo_url (str): The URL of the ontology logo
        level (str): The level of the ontology (e.g., 'TOP_LEVEL', 'MID_LEVEL', 'DOMAIN', 'USE_CASE')
        display_relations_names (bool): Whether to display relation names in the visualization
    """

    class_uri: Annotated[
        str, Field(..., description="The URI of the class to convert to YAML")
    ]


class CreateClassOntologyYamlWorkflow(Workflow):
    """Workflow for converting ontology files to YAML and pushing them to a Naas workspace."""

    __configuration: CreateClassOntologyYamlWorkflowConfiguration

    def __init__(self, configuration: CreateClassOntologyYamlWorkflowConfiguration):
        self.__configuration = configuration
        self.__convert_ontology_graph_workflow = ConvertOntologyGraphToYamlWorkflow(
            self.__configuration.convert_ontology_graph_config
        )

    def trigger(
        self, event: OntologyEvent, triple: tuple[Any, Any, Any]
    ) -> Union[str, None]:
        s, p, o = triple
        # logger.debug(f"==> Triggering Create Class Ontology YAML Workflow: {s} {p} {o}")
        if (
            str(event) != str(OntologyEvent.INSERT)
            or not str(o).startswith("http")
            or str(o) == "http://www.w3.org/2002/07/owl#NamedIndividual"
        ):
            # logger.debug(f"==> Skipping class ontology YAML creation for {s} {p} {o}")
            return None

        # Get class type from URI
        class_uri = get_class_uri_from_individual_uri(s)
        class_uri_triggers = [
            "https://www.commoncoreontologies.org/ont00001262",  # Person
            "https://www.commoncoreontologies.org/ont00000443",  # Commercial Organization
        ]
        if class_uri in class_uri_triggers:
            logger.debug(
                f"==> Creating class ontology YAML for {class_uri} ({s} {p} {o})"
            )
            return self.graph_to_yaml(
                CreateClassOntologyYamlWorkflowParameters(class_uri=class_uri)
            )
        return None

    def graph_to_yaml(
        self, parameters: CreateClassOntologyYamlWorkflowParameters
    ) -> str:
        # Initialize graph
        graph = Graph()
        graph.bind("abi", "http://ontology.naas.ai/abi/")

        # Get label and description from class uri
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?label ?definition
        WHERE {{
            <{parameters.class_uri}> rdfs:label ?label .
            <{parameters.class_uri}> skos:definition ?definition .
        }}
        """
        results = services.triple_store_service.query(query)
        result_list = results_to_list(results)
        if result_list:
            ontology_label = result_list[0]["label"]
            ontology_description = result_list[0]["definition"]
        else:
            ontology_label = ""
            ontology_description = ""

        # Get triples from class uri
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?subject ?predicate ?object
        WHERE {{
            ?subject a <{parameters.class_uri}> .
            ?subject ?predicate ?object .
        }}
        ORDER BY ?subject ?predicate
        """
        results = services.triple_store_service.query(query)
        list_uri = []
        # Add triples to graph
        for row in results:
            subject = URIRef(row.get("subject"))
            predicate = URIRef(row.get("predicate"))
            obj = row.get("object")

            # Add triple to graph
            if isinstance(obj, str) and obj.startswith("http://ontology.naas.ai/abi/"):
                obj = URIRef(obj)
                list_uri.append(obj)
            else:
                obj = Literal(obj)
            graph.add((subject, predicate, obj))

        # Get all object properties label and type
        if len(list_uri) > 0:
            # Filter only ABI URIs
            uri_filter = (
                "(" + " || ".join([f"?object = <{uri}>" for uri in list_uri]) + ")"
            )
            query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT DISTINCT ?object ?label ?type
            WHERE {{
            ?object rdfs:label ?label .
            ?object rdf:type ?type .
            FILTER {uri_filter}
            }}
            ORDER BY ?object
            """
            results = services.triple_store_service.query(query)

            # Add object properties to graph
            for row in results:
                graph.add(
                    (URIRef(row.get("object")), RDF.type, URIRef(row.get("type")))
                )
                graph.add((URIRef(row.get("object")), RDF.type, OWL.NamedIndividual))
                graph.add(
                    (URIRef(row.get("object")), RDFS.label, Literal(row.get("label")))
                )

        # Convert graph to YAML & push to Naas workspace
        ontology_id = self.__convert_ontology_graph_workflow.graph_to_yaml(
            ConvertOntologyGraphToYamlWorkflowParameters(
                graph=graph.serialize(format="turtle"),
                label=ontology_label,
                description=ontology_description,
            )
        )
        return ontology_id

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="ontology_create_class_yaml",
                description="Create an ontology class YAML and push it to Naas workspace.",
                func=lambda **kwargs: self.graph_to_yaml(
                    CreateClassOntologyYamlWorkflowParameters(**kwargs)
                ),
                args_schema=CreateClassOntologyYamlWorkflowParameters,
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

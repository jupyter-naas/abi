from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Union

from abi.services.triple_store.TripleStorePorts import (
    ITripleStoreService,
    OntologyEvent,
)
from abi.utils.Graph import URI_REGEX
from abi.utils.SPARQL import SPARQLUtils
from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field
from rdflib import RDFS, Graph, Literal, URIRef

from src.core.abi import ABIModule
from src.core.abi.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflow,
    ConvertOntologyGraphToYamlWorkflowConfiguration,
    ConvertOntologyGraphToYamlWorkflowParameters,
)


@dataclass
class CreateIndividualOntologyYamlWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateOntologyYAML workflow.

    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """

    triple_store: ITripleStoreService
    convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration


class CreateIndividualOntologyYamlWorkflowParameters(WorkflowParameters):
    """Parameters for CreateOntologyYAML workflow execution.

    Attributes:
        ontology_name (str): The name of the ontology store to use
        label (str): The label of the ontology
        description (str): The description of the ontology
        logo_url (str): The URL of the ontology logo
        level (str): The level of the ontology (e.g., 'TOP_LEVEL', 'MID_LEVEL', 'DOMAIN', 'USE_CASE')
        display_relations_names (bool): Whether to display relation names in the visualization
    """

    individual_uri: Annotated[
        str,
        Field(
            ...,
            description="The URI of the individual to convert to YAML",
            pattern=URI_REGEX,
        ),
    ]
    depth: Annotated[
        int,
        Field(
            description="The depth of the subject graph to get. 1 means the individual and its direct properties, 2 means the individual and its direct properties and the properties of the properties, etc."
        ),
    ] = 2


class CreateIndividualOntologyYamlWorkflow(Workflow):
    """Workflow for converting ontology files to YAML and pushing them to a Naas workspace."""

    __configuration: CreateIndividualOntologyYamlWorkflowConfiguration
    __sparql_utils: SPARQLUtils

    def __init__(
        self, configuration: CreateIndividualOntologyYamlWorkflowConfiguration
    ):
        self.__configuration = configuration
        self.__convert_ontology_graph_workflow = ConvertOntologyGraphToYamlWorkflow(
            self.__configuration.convert_ontology_graph_config
        )
        self.__sparql_utils: SPARQLUtils = SPARQLUtils(
            ABIModule.get_instance().engine.services.triple_store
        )

    def trigger(
        self, event: OntologyEvent, triple: tuple[Any, Any, Any]
    ) -> Union[str, None]:
        s, p, o = triple
        if (
            str(event) != str(OntologyEvent.INSERT)
            or not str(s).startswith("http://ontology.naas.ai/abi/")
            or not str(o).startswith("http://ontology.naas.ai/abi/")
        ):
            return None

        # Get class type from URI
        class_uri = self.__sparql_utils.get_class_uri_from_individual_uri(s)
        class_uri_triggers = [
            "https://www.commoncoreontologies.org/ont00001262",  # Person
            "https://www.commoncoreontologies.org/ont00000443",  # Commercial Organization
        ]
        if class_uri in class_uri_triggers:
            return self.graph_to_yaml(
                CreateIndividualOntologyYamlWorkflowParameters(
                    individual_uri=s, depth=2
                )
            )
        return None

    def graph_to_yaml(
        self, parameters: CreateIndividualOntologyYamlWorkflowParameters
    ) -> Union[str, None]:
        # Create individual graph
        graph = self.__sparql_utils.get_subject_graph(
            parameters.individual_uri, parameters.depth
        )

        # Get label from individual URI
        ontology_id = None
        ontology_label = ""
        ontology_description = ""
        ontology_logo_url = ""
        new_ontology = True
        for s, p, o in graph:
            if s == URIRef(parameters.individual_uri) and p == RDFS.label:
                ontology_label = str(o)
                ontology_description = f"{ontology_label} Ontology"
            if (
                s == URIRef(parameters.individual_uri)
                and str(p) == "http://ontology.naas.ai/abi/logo"
            ):
                ontology_logo_url = str(o)
            if (
                s == URIRef(parameters.individual_uri)
                and str(p) == "http://ontology.naas.ai/abi/naas_ontology_id"
            ):
                ontology_id = str(o)
                new_ontology = False

        # Convert graph to YAML & push to Naas workspace
        ontology_id = self.__convert_ontology_graph_workflow.graph_to_yaml(
            ConvertOntologyGraphToYamlWorkflowParameters(
                graph=graph.serialize(format="turtle"),
                ontology_id=ontology_id,
                label=ontology_label,
                description=ontology_description,
                logo_url=ontology_logo_url,
            )
        )
        if new_ontology:
            graph_insert = Graph()
            graph_insert.add(
                (
                    URIRef(parameters.individual_uri),
                    URIRef("http://ontology.naas.ai/abi/naas_ontology_id"),
                    Literal(ontology_id),
                )
            )
            self.__configuration.triple_store.insert(graph_insert)
        return ontology_id

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="create_individual_ontology_yaml",
                description="Create or Update a YAML ontology from an individual/instance in triple store and push it to Naas workspace.",
                func=lambda **kwargs: self.graph_to_yaml(
                    CreateIndividualOntologyYamlWorkflowParameters(**kwargs)
                ),
                args_schema=CreateIndividualOntologyYamlWorkflowParameters,
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

import os
from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi import ABIModule
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.StorageUtils import StorageUtils
from pydantic import Field
from rdflib import Graph, Namespace, URIRef
from rdflib.query import ResultRow

# Define namespaces
BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")


@dataclass
class RemoveIndividualPipelineConfiguration(PipelineConfiguration):
    """Configuration for RemoveIndividualPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService
    datastore_path: str = "knowledge_graph/remove"


class RemoveIndividualPipelineParameters(PipelineParameters):
    uri: Annotated[
        str,
        Field(description="URI to remove from the ontology"),
    ]
    graph_names: Annotated[
        list[str],
        Field(description="Graph names to remove the individual from"),
    ]


class RemoveIndividualPipeline(Pipeline):
    """Pipeline for removing individuals from the ontology."""

    __configuration: RemoveIndividualPipelineConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: RemoveIndividualPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils: StorageUtils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

    def get_all_triples_for_uri(self, uri: str, graph_uri: str):
        """
        Retrieve all triples where the given URI appears as either a subject or object.

        Args:
            uri (str): The URI to search for

        Returns:
            rdflib.query.Result: Query results containing all triples where the URI appears
        """
        sparql_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT ?s ?p ?o
        WHERE {{
            GRAPH <{graph_uri}> {{
                {{
                    # Find triples where the URI is the subject
                    <{uri}> ?p ?o .
                    BIND(<{uri}> AS ?s)
                }}
                UNION
                {{
                    # Find triples where the URI is the object
                    ?s ?p <{uri}> .
                    BIND(<{uri}> AS ?o)
                }}
            }}
        }}
        """

        return self.__configuration.triple_store.query(sparql_query)

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, RemoveIndividualPipelineParameters):
            raise ValueError(
                "Parameters must be of type RemoveIndividualPipelineParameters"
            )

        removed_graph = Graph()

        for graph_uri in parameters.graph_names:
            graph_name = graph_uri.split("/")[-1]
            output_dir = os.path.join(self.__configuration.datastore_path, graph_name)

            results = self.get_all_triples_for_uri(str(parameters.uri), graph_uri)
            rows = list(results)
            logger.debug(
                f"Found {len(rows)} triples for URI: {parameters.uri} in graph: {graph_uri}"
            )

            if not rows:
                continue

            graph = Graph()
            for row in rows:
                assert isinstance(row, ResultRow)
                s, p, o = row
                graph.add((s, p, o))

            logger.debug(f"✅ Removing {len(graph)} triples for URI: {parameters.uri}")
            self.__storage_utils.save_triples(
                graph, output_dir, f"{parameters.uri.split('/')[-1]}.ttl"
            )
            self.__configuration.triple_store.remove(graph, graph_name=URIRef(graph_uri))
            removed_graph += graph

        return removed_graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="remove_individuals",
                description="Remove individuals from the triplestore by deleting all their associated triples",
                func=lambda **kwargs: self.run(
                    RemoveIndividualPipelineParameters(**kwargs)
                ),
                args_schema=RemoveIndividualPipelineParameters,
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

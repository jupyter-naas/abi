from dataclasses import dataclass
from enum import Enum
from typing import Annotated, List

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi import ABIModule, logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.StorageUtils import StorageUtils
from pydantic import Field
from rdflib import Graph, Namespace

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
    datastore_path: str = "datastore/ontology/removed_individual"


class RemoveIndividualPipelineParameters(PipelineParameters):
    uris_to_remove: Annotated[
        List[str],
        Field(description="List of URIs to remove from the ontology", min_items=1),
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

    def get_all_triples_for_uri(self, uri: str):
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
        """

        return self.__configuration.triple_store.query(sparql_query)

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, RemoveIndividualPipelineParameters):
            raise ValueError(
                "Parameters must be of type RemoveIndividualPipelineParameters"
            )

        output_dir = self.__configuration.datastore_path
        removed_graph = Graph()
        removed_graph.bind("bfo", BFO)
        removed_graph.bind("cco", CCO)
        removed_graph.bind("abi", ABI)

        for uri in parameters.uris_to_remove:
            logger.info(f"Getting triples for URI: {uri}")
            results = self.get_all_triples_for_uri(uri)
            graph_remove = Graph()

            for row in results:
                s, p, o = row
                graph_remove.add((s, p, o))

            if len(graph_remove) > 0:
                logger.info(f"✅ Removing {len(graph_remove)} triples for URI: {uri}")
                logger.info(graph_remove.serialize(format="turtle"))
                self.__storage_utils.save_triples(
                    graph_remove, output_dir, f"{uri.split('/')[-1]}.ttl"
                )
                self.__configuration.triple_store.remove(graph_remove)

                # Add to the combined removed graph for return
                for triple in graph_remove:
                    removed_graph.add(triple)
            else:
                logger.info(f"No triples found for {uri}")

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


if __name__ == "__main__":
    from naas_abi import services

    uris_to_remove = [
        "http://ontology.naas.ai/abi/example-uri-1",
        "http://ontology.naas.ai/abi/example-uri-2",
    ]

    configuration = RemoveIndividualPipelineConfiguration(
        triple_store=services.triple_store_service
    )

    pipeline = RemoveIndividualPipeline(configuration)
    graph = pipeline.run(
        RemoveIndividualPipelineParameters(
            uris_to_remove=uris_to_remove,
        )
    )
    logger.info(graph.serialize(format="turtle"))

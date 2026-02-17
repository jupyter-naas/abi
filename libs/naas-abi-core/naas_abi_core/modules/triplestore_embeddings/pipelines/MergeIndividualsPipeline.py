from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated

from langchain_core.tools import BaseTool
from naas_abi_core import logger
from naas_abi_core.modules.triplestore_embeddings import ABIModule
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_core.utils.StorageUtils import StorageUtils
from pydantic import Field
from rdflib import RDFS, SKOS, Graph, Literal, Namespace, URIRef

# Define namespaces
BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")


@dataclass
class MergeIndividualsPipelineConfiguration(PipelineConfiguration):
    """Configuration for MergeIndividualsPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: TripleStoreService
    object_storage: ObjectStorageService
    graph_name: URIRef | str | None = None
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )


class MergeIndividualsPipelineParameters(PipelineParameters):
    merge_pairs: Annotated[
        list[tuple[str, str]],
        Field(
            description="List of tuples where each tuple contains (uri_to_keep, uri_to_merge). "
            "The first URI will remain and receive the merged triples, "
            "the second URI will be merged into the first and then removed.",
        ),
    ]


class MergeIndividualsPipeline(Pipeline):
    """Pipeline for merging two individuals in the ontology."""

    __configuration: MergeIndividualsPipelineConfiguration
    __sparql_utils: SPARQLUtils
    __storage_utils: StorageUtils
    __graph_name: URIRef | None = None

    def __init__(self, configuration: MergeIndividualsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__triple_store_service = self.__configuration.triple_store
        self.__object_storage_service = self.__configuration.object_storage
        self.__sparql_utils: SPARQLUtils = SPARQLUtils(self.__triple_store_service)
        self.__storage_utils: StorageUtils = StorageUtils(self.__object_storage_service)
        if self.__configuration.graph_name is not None:
            self.__graph_name = URIRef(self.__configuration.graph_name)
        else:
            self.__graph_name = None

    def get_all_triples_for_uri(self, uri: str, graph_name: URIRef | str | None = None):
        """
        Retrieve all triples where the given URI appears as either a subject or object.

        Args:
            uri (str): The URI to search for
            graph_name: Optional graph name. If None, uses self.__graph_name from configuration.

        Returns:
            rdflib.query.Result: Query results containing all triples where the URI appears
        """
        if graph_name is None:
            graph_clause = ""
            graph_close = ""
        else:
            graph_clause = f"GRAPH <{str(graph_name)}> {{"
            graph_close = "}"

        sparql_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT ?s ?p ?o
        WHERE {{
            {graph_clause}
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
            {graph_close}
        }}
        """

        return self.__configuration.triple_store.query(sparql_query)

    def _merge_single_pair(self, uri_to_keep: str, uri_to_merge: str) -> Graph:
        """
        Merge a single pair of individuals.

        Args:
            uri_to_keep: The URI that will remain and receive the merged triples
            uri_to_merge: The URI that will be merged into uri_to_keep and then removed
            output_dir: Directory path for saving output files

        Returns:
            Graph: The graph of the merged individual (uri_to_keep)
        """
        # Get all triples to keep
        keep_results = list(
            self.get_all_triples_for_uri(uri_to_keep, self.__graph_name)
        )
        keep_graph = Graph()
        for row in keep_results:
            s, p, o = row
            keep_graph.add((s, p, o))
        logger.info(f"Found {len(keep_results)} triples for URI to keep: {uri_to_keep}")

        # Get all triples to merge
        merge_results = list(
            self.get_all_triples_for_uri(uri_to_merge, self.__graph_name)
        )
        merge_graph = Graph()
        for row in merge_results:
            s, p, o = row
            merge_graph.add((s, p, o))
        logger.info(
            f"Found {len(merge_results)} triples for URI to merge: {uri_to_merge}"
        )

        if len(merge_results) == 0:
            logger.warning(f"No triples found for URI to merge: {uri_to_merge}")
            return keep_graph

        # Init graphs
        graph_insert = Graph()
        graph_insert.bind("bfo", BFO)
        graph_insert.bind("cco", CCO)
        graph_insert.bind("abi", ABI)
        graph_remove = Graph()

        # Init URIs
        uri_to_keep_ref = URIRef(uri_to_keep)
        uri_to_keep_label = keep_graph.value(uri_to_keep_ref, RDFS.label)
        uri_to_merge_ref = URIRef(uri_to_merge)
        uri_to_merge_label = merge_graph.value(uri_to_merge_ref, RDFS.label)

        # Process triples to merge
        logger.info(
            f"Merging '{uri_to_merge_label}' ({uri_to_merge}) into '{uri_to_keep_label}' ({uri_to_keep})"
        )
        for row in merge_results:
            s, p, o = row
            # Add all triples except RDFS.label
            if s == uri_to_merge_ref and p not in [RDFS.label]:
                check_properties = keep_graph.triples((uri_to_keep_ref, p, o))
                if len(list(check_properties)) == 0:
                    if isinstance(o, URIRef):
                        graph_insert.add((uri_to_keep_ref, URIRef(p), URIRef(o)))
                    elif isinstance(o, Literal):
                        datatype = o.datatype if hasattr(o, "datatype") else None
                        lang = o.language if hasattr(o, "language") else None
                        graph_insert.add(
                            (
                                uri_to_keep_ref,
                                URIRef(p),
                                Literal(str(o), datatype=datatype, lang=lang),
                            )
                        )
            # Specific use case for RDFS.label
            # 1. We don't want to merge "unknown" labels
            # 2. We want to add the label to be be merged to altLabel property to keep track of the original label
            elif (
                s == uri_to_merge_ref
                and p in [RDFS.label]
                and str(o).lower() != "unknown"
            ):
                datatype = o.datatype if hasattr(o, "datatype") else None
                lang = o.language if hasattr(o, "language") else None
                graph_insert.add(
                    (
                        uri_to_keep_ref,
                        SKOS.altLabel,
                        Literal(str(o), datatype=datatype, lang=lang),
                    )
                )

            # Add all triples where the object is the URI to merge
            elif o == uri_to_merge_ref:
                check_properties = keep_graph.triples((s, p, uri_to_keep_ref))
                if len(list(check_properties)) == 0:
                    graph_insert.add((s, p, uri_to_keep_ref))

            # Always add original triple for removal to the graph to remove
            graph_remove.add((s, p, o))

        # Save and insert graphs
        if len(graph_insert) > 0:
            logger.info(f"Inserting {len(graph_insert)} triples")
            logger.debug(graph_insert.serialize(format="turtle"))
            self.__storage_utils.save_triples(
                graph_insert,
                self.__configuration.datastore_path + "/merged_individual",
                f"{uri_to_keep_label}_{uri_to_keep.split('/')[-1]}_merged.ttl",
            )
            self.__configuration.triple_store.insert(
                graph_insert, graph_name=self.__graph_name
            )
        if len(graph_remove) > 0:
            logger.info(f"Removing {len(graph_remove)} triples")
            logger.debug(graph_remove.serialize(format="turtle"))
            self.__storage_utils.save_triples(
                graph_remove,
                self.__configuration.datastore_path + "/merged_individual",
                f"{uri_to_merge_label}_{uri_to_merge.split('/')[-1]}_removed.ttl",
            )
            self.__configuration.triple_store.remove(
                graph_remove, graph_name=self.__graph_name
            )

        return self.__sparql_utils.get_subject_graph(uri_to_keep)

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, MergeIndividualsPipelineParameters):
            raise ValueError(
                "Parameters must be of type MergeIndividualsPipelineParameters"
            )

        merged_graph = Graph()

        logger.info(f"Processing {len(parameters.merge_pairs)} merge operation(s)")
        for idx, (uri_to_keep, uri_to_merge) in enumerate(parameters.merge_pairs, 1):
            logger.info(
                f"Processing merge operation {idx}/{len(parameters.merge_pairs)}"
            )
            result_graph = self._merge_single_pair(uri_to_keep, uri_to_merge)
            merged_graph += result_graph

        return merged_graph

    def as_tools(self) -> list[BaseTool]:
        return []

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

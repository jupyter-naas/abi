from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi import ABIModule
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageDomain,
)
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.Graph import URI_REGEX
from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_core.utils.StorageUtils import StorageUtils
from pydantic import Field, field_validator
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

    triple_store: ITripleStoreService
    object_storage: IObjectStorageDomain
    datastore_path: str = "datastore/ontology/merged_individual"


class MergeIndividualsPipelineParameters(PipelineParameters):
    merge_pairs: Annotated[
        list[tuple[str, str]],
        Field(
            description="List of tuples where each tuple contains (uri_to_keep, uri_to_merge). "
            "The first URI will remain and receive the merged triples, "
            "the second URI will be merged into the first and then removed.",
        ),
    ]

    @field_validator("merge_pairs")
    @classmethod
    def validate_merge_pairs(cls, v):
        """Validate that all URIs in merge pairs match the URI_REGEX pattern."""
        import re

        if not v:
            raise ValueError("merge_pairs cannot be empty")
        for pair in v:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError(
                    "Each merge pair must be a tuple of exactly 2 elements"
                )
            uri_to_keep, uri_to_merge = pair
            if not isinstance(uri_to_keep, str) or not isinstance(uri_to_merge, str):
                raise ValueError("Both URIs in a merge pair must be strings")
            if not re.match(URI_REGEX, uri_to_keep):
                raise ValueError(
                    f"uri_to_keep '{uri_to_keep}' does not match URI pattern"
                )
            if not re.match(URI_REGEX, uri_to_merge):
                raise ValueError(
                    f"uri_to_merge '{uri_to_merge}' does not match URI pattern"
                )
            if uri_to_keep == uri_to_merge:
                raise ValueError("uri_to_keep and uri_to_merge cannot be the same URI")
        return v


class MergeIndividualsPipeline(Pipeline):
    """Pipeline for merging two individuals in the ontology."""

    __configuration: MergeIndividualsPipelineConfiguration
    __sparql_utils: SPARQLUtils
    __storage_utils: StorageUtils

    def __init__(self, configuration: MergeIndividualsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__triple_store_service = self.__configuration.triple_store
        self.__object_storage_service = self.__configuration.object_storage
        self.__sparql_utils: SPARQLUtils = SPARQLUtils(self.__triple_store_service)
        self.__storage_utils: StorageUtils = StorageUtils(self.__object_storage_service)

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

    def _merge_single_pair(
        self, uri_to_keep: str, uri_to_merge: str, output_dir: str
    ) -> Graph:
        """
        Merge a single pair of individuals.

        Args:
            uri_to_keep: The URI that will remain and receive the merged triples
            uri_to_merge: The URI that will be merged into uri_to_keep and then removed
            output_dir: Directory path for saving output files

        Returns:
            Graph: The graph of the merged individual (uri_to_keep)
        """
        # Get all triples for both URIs
        keep_results = list(self.get_all_triples_for_uri(uri_to_keep))
        keep_graph = Graph()
        for row in keep_results:
            s, p, o = row
            keep_graph.add((s, p, o))
        logger.info(f"Found {len(keep_results)} triples for URI to keep: {uri_to_keep}")

        merge_results = list(self.get_all_triples_for_uri(uri_to_merge))
        merge_graph = Graph()
        for row in merge_results:
            s, p, o = row
            merge_graph.add((s, p, o))
        logger.info(
            f"Found {len(merge_results)} triples for URI to merge: {uri_to_merge}"
        )

        graph_insert = Graph()
        graph_insert.bind("bfo", BFO)
        graph_insert.bind("cco", CCO)
        graph_insert.bind("abi", ABI)
        graph_remove = Graph()
        uri_to_keep_ref = URIRef(uri_to_keep)
        uri_to_keep_label = keep_graph.value(uri_to_keep_ref, RDFS.label)
        uri_to_merge_ref = URIRef(uri_to_merge)
        uri_to_merge_label = merge_graph.value(uri_to_merge_ref, RDFS.label)

        # Process triples from uri_to_merge
        logger.info(
            f"Merging '{uri_to_merge_label}' ({uri_to_merge}) into '{uri_to_keep_label}' ({uri_to_keep})"
        )
        for row in merge_results:
            s, p, o = row
            if s == uri_to_merge_ref and p not in [RDFS.label, ABI.universal_name]:
                check_properties = keep_graph.triples((uri_to_keep_ref, p, o))
                if len(list(check_properties)) == 0:
                    if isinstance(o, URIRef):
                        graph_insert.add((uri_to_keep_ref, URIRef(p), URIRef(o)))
                    elif isinstance(o, Literal):
                        # Preserve datatype and language tag if present
                        datatype = o.datatype if hasattr(o, "datatype") else None
                        lang = o.language if hasattr(o, "language") else None
                        graph_insert.add(
                            (
                                uri_to_keep_ref,
                                URIRef(p),
                                Literal(str(o), datatype=datatype, lang=lang),
                            )
                        )

            elif s == uri_to_merge_ref and p in [RDFS.label, ABI.universal_name]:
                datatype = o.datatype if hasattr(o, "datatype") else None
                lang = o.language if hasattr(o, "language") else None
                graph_insert.add(
                    (
                        uri_to_keep_ref,
                        SKOS.altLabel,
                        Literal(str(o), datatype=datatype, lang=lang),
                    )
                )

            elif o == uri_to_merge_ref:
                check_properties = keep_graph.triples((s, p, uri_to_keep_ref))
                if len(list(check_properties)) == 0:
                    graph_insert.add((s, p, uri_to_keep_ref))

            # Always add original triple for removal
            graph_remove.add((s, p, o))

        if len(graph_insert) > 0:
            logger.info(f"✅ Inserting {len(graph_insert)} triples")
            logger.info(graph_insert.serialize(format="turtle"))
            self.__storage_utils.save_triples(
                graph_insert,
                output_dir,
                f"{uri_to_keep_label}_{uri_to_keep.split('/')[-1]}_merged.ttl",
            )
            self.__configuration.triple_store.insert(graph_insert)
        if len(graph_remove) > 0:
            logger.info(f"✅ Removing {len(graph_remove)} triples")
            logger.info(graph_remove.serialize(format="turtle"))
            self.__storage_utils.save_triples(
                graph_remove,
                output_dir,
                f"{uri_to_merge_label}_{uri_to_merge.split('/')[-1]}_removed.ttl",
            )
            self.__configuration.triple_store.remove(graph_remove)

        return self.__sparql_utils.get_subject_graph(uri_to_keep)

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, MergeIndividualsPipelineParameters):
            raise ValueError(
                "Parameters must be of type MergeIndividualsPipelineParameters"
            )

        output_dir = self.__configuration.datastore_path
        merged_graph = Graph()

        logger.info(f"Processing {len(parameters.merge_pairs)} merge operation(s)")
        for idx, (uri_to_keep, uri_to_merge) in enumerate(parameters.merge_pairs, 1):
            logger.info(
                f"Processing merge operation {idx}/{len(parameters.merge_pairs)}"
            )
            result_graph = self._merge_single_pair(
                uri_to_keep, uri_to_merge, output_dir
            )
            merged_graph += result_graph

        return merged_graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="merge_individuals",
                description="Merge multiple pairs of individuals in the triplestore by transferring all triples from one to another. "
                "Takes a list of tuples where each tuple contains (uri_to_keep, uri_to_merge).",
                func=lambda **kwargs: self.run(
                    MergeIndividualsPipelineParameters(**kwargs)
                ),
                args_schema=MergeIndividualsPipelineParameters,
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
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.domains.ontology_engineer"])
    triple_store_service = ABIModule.get_instance().engine.services.triple_store
    object_storage_service = ABIModule.get_instance().engine.services.object_storage

    uri_to_keep = "http://ontology.naas.ai/abi/69a231b9-e87a-4503-8f80-a530ed8eaa4b"  # URI that will remain
    uri_to_merge = "http://ontology.naas.ai/abi/4f92bbdd-e710-4e43-9480-9b6cd6d9af80"  # URI that will be merged and removed

    configuration = MergeIndividualsPipelineConfiguration(
        triple_store=triple_store_service,
        object_storage=object_storage_service,
    )

    pipeline = MergeIndividualsPipeline(configuration)
    graph = pipeline.run(
        MergeIndividualsPipelineParameters(
            merge_pairs=[
                (uri_to_keep, uri_to_merge),
            ]
        )
    )
    logger.info(f"Merged graph: {len(graph)} triples")
    logger.info(graph.serialize(format="turtle"))

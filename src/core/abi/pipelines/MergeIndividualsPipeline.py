from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from pydantic import Field
from typing import Annotated
from rdflib import URIRef, Literal, Graph, RDFS, SKOS, Namespace
from abi.utils.Graph import URI_REGEX
from fastapi import APIRouter
from enum import Enum
from abi import logger
from src.utils.SPARQL import get_subject_graph
from src.utils.Storage import save_triples

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
    datastore_path: str = "datastore/ontology/merged_individual"

class MergeIndividualsPipelineParameters(PipelineParameters):
    uri_to_keep: Annotated[str, Field(
        description="The URI that will remain and receive the merged triples",
        pattern=URI_REGEX
    )]
    uri_to_merge: Annotated[str, Field(
        description="The URI that will be merged into uri_to_keep and then removed",
        pattern=URI_REGEX
    )]

class MergeIndividualsPipeline(Pipeline):
    """Pipeline for merging two individuals in the ontology."""

    __configuration: MergeIndividualsPipelineConfiguration

    def __init__(self, configuration: MergeIndividualsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

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
        if not isinstance(parameters, MergeIndividualsPipelineParameters):
            raise ValueError("Parameters must be of type MergeIndividualsPipelineParameters")
        
        output_dir = self.__configuration.datastore_path
        
        # Get all triples for both URIs
        keep_results = self.get_all_triples_for_uri(parameters.uri_to_keep)
        keep_graph = Graph()
        for row in keep_results:
            s, p, o = row
            keep_graph.add((s, p, o))
        logger.info(f"Found {len(keep_results)} triples for URI to keep: {parameters.uri_to_keep}")
        
        merge_results = self.get_all_triples_for_uri(parameters.uri_to_merge)
        merge_graph = Graph()
        for row in merge_results:
            s, p, o = row
            merge_graph.add((s, p, o))
        logger.info(f"Found {len(merge_results)} triples for URI to merge: {parameters.uri_to_merge}")

        graph_insert = Graph()
        graph_insert.bind("bfo", BFO)
        graph_insert.bind("cco", CCO)
        graph_insert.bind("abi", ABI)
        graph_remove = Graph()
        uri_to_keep_ref = URIRef(parameters.uri_to_keep)
        uri_to_keep_label = keep_graph.value(uri_to_keep_ref, RDFS.label)
        uri_to_merge_ref = URIRef(parameters.uri_to_merge)
        uri_to_merge_label = merge_graph.value(uri_to_merge_ref, RDFS.label)
        
        # Process triples from uri_to_merge
        logger.info(f"Merging '{uri_to_merge_label}' ({parameters.uri_to_merge}) into '{uri_to_keep_label}' ({parameters.uri_to_keep})")
        for row in merge_results:
            s, p, o = row
            if s == uri_to_merge_ref and p not in [RDFS.label, ABI.universal_name]:
                check_properties = keep_graph.triples((uri_to_keep_ref, p, o))
                if len(list(check_properties)) == 0:
                    if isinstance(o, URIRef):
                        graph_insert.add((uri_to_keep_ref, URIRef(p), URIRef(o)))
                    elif isinstance(o, Literal):
                        # Preserve datatype and language tag if present
                        datatype = o.datatype if hasattr(o, 'datatype') else None
                        lang = o.language if hasattr(o, 'language') else None
                        graph_insert.add((uri_to_keep_ref, URIRef(p), Literal(str(o), datatype=datatype, lang=lang)))

            elif s == uri_to_merge_ref and p in [RDFS.label, ABI.universal_name]:
                datatype = o.datatype if hasattr(o, 'datatype') else None
                lang = o.language if hasattr(o, 'language') else None
                graph_insert.add((uri_to_keep_ref, SKOS.altLabel, Literal(str(o), datatype=datatype, lang=lang)))
                        
            elif o == uri_to_merge_ref:
                check_properties = keep_graph.triples((s, p, uri_to_keep_ref))
                if len(list(check_properties)) == 0:
                    graph_insert.add((s, p, uri_to_keep_ref))

            # Always add original triple for removal
            graph_remove.add((s, p, o))

        if len(graph_insert) > 0:
            logger.info(f"✅ Inserting {len(graph_insert)} triples")
            logger.info(graph_insert.serialize(format='turtle'))
            save_triples(graph_insert, output_dir, f"{uri_to_keep_label}_{parameters.uri_to_keep.split('/')[-1]}_merged.ttl")
            self.__configuration.triple_store.insert(graph_insert)
        if len(graph_remove) > 0:
            logger.info(f"✅ Removing {len(graph_remove)} triples")
            logger.info(graph_remove.serialize(format='turtle'))
            save_triples(graph_remove, output_dir, f"{uri_to_merge_label}_{parameters.uri_to_merge.split('/')[-1]}_removed.ttl")
            self.__configuration.triple_store.remove(graph_remove)
        
        return get_subject_graph(parameters.uri_to_keep)

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="merge_individuals",
                description="Merge two individuals in the triplestore by transferring all triples from one to another",
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
    from src import services

    uri_to_keep = "http://ontology.naas.ai/abi/69a231b9-e87a-4503-8f80-a530ed8eaa4b"  # URI that will remain
    uri_to_merge = "http://ontology.naas.ai/abi/4f92bbdd-e710-4e43-9480-9b6cd6d9af80" # URI that will be merged and removed
    
    configuration = MergeIndividualsPipelineConfiguration(
        triple_store=services.triple_store_service
    )
    
    pipeline = MergeIndividualsPipeline(configuration)
    graph = pipeline.run(MergeIndividualsPipelineParameters(
        uri_to_keep=uri_to_keep,
        uri_to_merge=uri_to_merge,
    ))
    logger.info(graph.serialize(format="turtle"))
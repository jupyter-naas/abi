from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from pydantic import Field
from typing import Optional, List, Tuple
from rdflib import Graph, URIRef, Literal, Namespace, RDF, OWL, RDFS
import uuid

BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class AddIndividualProcessPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddIndividualProcessPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
    """
    triple_store: ITripleStoreService

class AddIndividualProcessPipelineParameters(PipelineParameters):
    process_uri: str = Field(..., description="URI for the process.")
    participants_uris: Optional[List[str]] = Field(None, description="URIs of participants in the process.")

class AddIndividualProcessPipeline(Pipeline):
    """Pipeline for adding a process individual with related object properties."""
    __configuration: AddIndividualProcessPipelineConfiguration
    
    def __init__(self, configuration: AddIndividualProcessPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: AddIndividualProcessPipelineParameters) -> Tuple[str, Graph]:
        # Init graph
        graph = Graph()
        graph.bind("bfo", BFO)
        graph.bind("cco", CCO)
        graph.bind("abi", ABI)

        # Add process individual
        process_uri = ABI[str(uuid.uuid4())]
        graph.add((process_uri, RDF.type, OWL.NamedIndividual))
        graph.add((process_uri, RDF.type, URIRef(parameters.class_uri)))
        graph.add((process_uri, RDFS.label, Literal(parameters.individual_label)))

        # Add object properties if provided
        if parameters.has_participant:
            for participant in parameters.has_participant:
                graph.add((process_uri, CCO.has_participant, URIRef(participant)))

        if parameters.has_agent:
            for agent in parameters.has_agent:
                graph.add((process_uri, CCO.has_agent, URIRef(agent)))

        if parameters.has_input:
            for input_uri in parameters.has_input:
                graph.add((process_uri, CCO.has_input, URIRef(input_uri)))

        if parameters.has_output:
            for output_uri in parameters.has_output:
                graph.add((process_uri, CCO.has_output, URIRef(output_uri)))

        self.__configuration.triple_store.insert(graph)
        return process_uri, graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_process",
                description="Add a new process individual to triple store with related object properties.",
                func=lambda **kwargs: self.run(AddIndividualProcessPipelineParameters(**kwargs)),
                args_schema=AddIndividualProcessPipelineParameters
            )
        ]

    def as_api(self) -> None:
        pass 
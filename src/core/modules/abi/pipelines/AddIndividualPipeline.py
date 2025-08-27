from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import (
    ITripleStoreService,
)
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from abi import logger
from pydantic import Field
from typing import Annotated, Optional
from rdflib import (
    Graph,
    URIRef,
    Literal,
    Namespace,
    RDF,
    OWL,
    RDFS,
    DCTERMS,
)
import uuid
from src.core.modules.abi.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflow,
    SearchIndividualWorkflowParameters,
    SearchIndividualWorkflowConfiguration,
)
from fastapi import APIRouter
from enum import Enum

BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")
URI_REGEX = r"http:\/\/ontology\.naas\.ai\/abi\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

@dataclass
class AddIndividualPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddIndividualPipeline.

    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
        search_individual_workflow (SearchIndividualWorkflow): The search individual workflow to use
    """

    triple_store: ITripleStoreService
    search_individual_configuration: SearchIndividualWorkflowConfiguration

class AddIndividualPipelineParameters(PipelineParameters):
    individual_label: Annotated[str, Field(
        description="Individual label to add to the ontology.",
        example="Naas.ai"
    )]
    class_uri: Annotated[str, Field(
        description="Class URI to add the individual to. Use tool `search_class` to search for a class URI in the ontology.",
        example="https://www.commoncoreontologies.org/ont00000443"
    )]
    threshold: Annotated[Optional[int], Field(
        description="Threshold to use for the search individual workflow.",
        default=90,
        ge=0,
        le=100
    )] = 80

class AddIndividualPipeline(Pipeline):
    """Pipeline for adding a named individual."""

    __configuration: AddIndividualPipelineConfiguration

    def __init__(self, configuration: AddIndividualPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__search_individual_workflow = SearchIndividualWorkflow(
            configuration.search_individual_configuration
        )

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, AddIndividualPipelineParameters):
            raise ValueError("Parameters must be of type AddIndividualPipelineParameters")
        
        # Search for individual
        search_individual_result = self.__search_individual_workflow.search_individual(
            SearchIndividualWorkflowParameters(
                class_uri=parameters.class_uri, 
                search_label=parameters.individual_label,
            )
        )
        filtered_results = [
            result for result in search_individual_result 
            if parameters.threshold is not None and int(result["score"]) >= parameters.threshold
        ]
        if len(filtered_results) > 0:
            individual_uri = filtered_results[0]["individual_uri"]
            logger.debug(
                f"🔍 Found individual '{parameters.individual_label}' in the ontology: {individual_uri} from class: {parameters.class_uri}"
            )
            return self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Init graph
        graph = Graph()
        graph.bind("bfo", BFO)
        graph.bind("cco", CCO)
        graph.bind("abi", ABI)
        graph.bind("dcterms", DCTERMS)

        # Add individual
        individual_uri = ABI[str(uuid.uuid4())]
        graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        graph.add((individual_uri, RDF.type, URIRef(parameters.class_uri)))
        graph.add((individual_uri, RDFS.label, Literal(parameters.individual_label)))
        self.__configuration.triple_store.insert(graph)
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="add_individual_to_triple_store",
                description="Add a new individual/instance to triple store.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(**kwargs)
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
            StructuredTool(
                name="add_commercial_organization",
                description="Add a new commercial organization to ontology.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(
                        class_uri="https://www.commoncoreontologies.org/ont00000443",
                        individual_label=kwargs["individual_label"]
                    )
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
            StructuredTool(
                name="add_person",
                description="Add a new person to ontology.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(
                        class_uri="https://www.commoncoreontologies.org/ont00001262",
                        individual_label=kwargs["individual_label"]
                    )
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
            StructuredTool(
                name="add_website",
                description="Add a new website to ontology.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(
                        class_uri=ABI.Website,
                        individual_label=kwargs["individual_label"]
                    )
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
            StructuredTool(
                name="add_skill",
                description="Add a new skill to ontology.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(
                        class_uri=CCO.ont00000089,
                        individual_label=kwargs["individual_label"]
                    )
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
            StructuredTool(
                name="add_legal_name",
                description="Add a new legal name of a commercial organization.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(
                        class_uri=CCO.ont00001331,
                        individual_label=kwargs["individual_label"]
                    )
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
            StructuredTool(
                name="add_ticker_symbol",
                description="Add a new ticker symbol to triple store.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(
                        class_uri=ABI.Ticker,
                        individual_label=kwargs["individual_label"]
                    )
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
            StructuredTool(
                name="add_linkedin_page",
                description="Add a new LinkedIn page represented by a profile or organization to triple store.",
                func=lambda **kwargs: self.run(
                    AddIndividualPipelineParameters(
                        class_uri=ABI.LinkedInProfilePage,
                        individual_label=kwargs["individual_label"]
                    )
                ),
                args_schema=AddIndividualPipelineParameters,
            ),
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

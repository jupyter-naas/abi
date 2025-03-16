from dataclasses import dataclass
from datetime import datetime
from rdflib import Graph
from pydantic import BaseModel, Field
from typing import Optional
from langchain_core.tools import StructuredTool
from fastapi import APIRouter

from abi.pipeline import Pipeline, PipelineConfiguration
from abi.utils.Graph import ABIGraph, ABI, BFO
from src.integrations.ArXivIntegration import ArXivIntegration, ArXivIntegrationConfiguration
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

@dataclass
class ArXivPaperPipelineConfiguration(PipelineConfiguration):
    """Configuration for ArXivPaperPipeline."""
    arxiv_integration_config: ArXivIntegrationConfiguration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "arxiv"

class ArXivPaperPipelineParameters(BaseModel):
    """Parameters for ArXivPaperPipeline."""
    paper_id: str = Field(..., description="ArXiv paper ID")

class ArXivPaperPipeline(Pipeline):
    """Pipeline for adding ArXiv papers to the ontology."""
    
    def __init__(self, configuration: ArXivPaperPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__arxiv_integration = ArXivIntegration(configuration.arxiv_integration_config)

    def run(self, parameters: ArXivPaperPipelineParameters) -> Graph:
        # Init graph
        try:
            existing_graph = self.__configuration.ontology_store.get(self.__configuration.ontology_store_name)
            graph = ABIGraph()
            for triple in existing_graph:
                graph.add(triple)
        except Exception:
            graph = ABIGraph()

        # Get paper data
        paper_data = self.__arxiv_integration.get_paper(parameters.paper_id)

        # Add paper to graph
        paper = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=paper_data["id"],
            label=paper_data["title"],
            is_a=ABI.ArXivPaper,
            description=paper_data["summary"],
            url=paper_data["pdf_url"],
            ontology_group=str(ABI.ArXivPaper).split("/")[-1]
        )

        # Add temporal information
        published_date = paper_data["published"]
        temporal_instant = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=str(int(published_date.timestamp())),
            label=published_date.strftime("%Y-%m-%dT%H:%M:%S%z"),
            is_a=BFO.BFO_0000203
        )
        graph.add((paper, BFO.BFO_0000222, temporal_instant))

        # Add authors
        for author_name in paper_data["authors"]:
            author = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=author_name.replace(" ", "_"),
                label=author_name,
                is_a=ABI.ArXivAuthor,
                ontology_group=str(ABI.ArXivAuthor).split("/")[-1]
            )
            graph.add((paper, ABI.hasAuthor, author))

        # Add categories
        for category in paper_data["categories"]:
            cat = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=category,
                label=category,
                is_a=ABI.ArXivCategory,
                ontology_group=str(ABI.ArXivCategory).split("/")[-1]
            )
            graph.add((paper, ABI.hasCategory, cat))

        self.__configuration.ontology_store.store(self.__configuration.ontology_store_name, graph)
        return graph

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="arxiv_paper_pipeline",
                description="Adds an ArXiv paper to the ontology",
                func=lambda **kwargs: self.run(ArXivPaperPipelineParameters(**kwargs)),
                args_schema=ArXivPaperPipelineParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/arxiv/paper")
        def run(parameters: ArXivPaperPipelineParameters):
            return self.run(parameters).serialize(format="turtle") 
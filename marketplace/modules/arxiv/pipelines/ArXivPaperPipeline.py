from dataclasses import dataclass
from datetime import datetime
import os
import uuid
import re
import requests
from rdflib import Graph
from pydantic import BaseModel, Field
from typing import Optional
from langchain_core.tools import StructuredTool
from fastapi import APIRouter

from abi.pipeline import Pipeline, PipelineConfiguration
from abi.utils.Graph import ABIGraph, ABI, BFO
from src.custom.modules.arxiv_agent.integrations.ArXivIntegration import ArXivIntegration, ArXivIntegrationConfiguration
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

@dataclass
class ArXivPaperPipelineConfiguration(PipelineConfiguration):
    """Configuration for ArXivPaperPipeline."""
    arxiv_integration_config: ArXivIntegrationConfiguration
    ontology_store: IOntologyStoreService
    storage_base_path: str = "storage/triplestore/application-level/arxiv"
    pdf_storage_path: str = "datastore/application-level/arxiv"

class ArXivPaperPipelineParameters(BaseModel):
    """Parameters for ArXivPaperPipeline."""
    paper_id: str = Field(..., description="ArXiv paper ID")
    download_pdf: bool = Field(True, description="Whether to download the paper's PDF")

class ArXivPaperPipeline(Pipeline):
    """Pipeline for adding ArXiv papers to the ontology."""
    
    def __init__(self, configuration: ArXivPaperPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__arxiv_integration = ArXivIntegration(configuration.arxiv_integration_config)
        
        # Ensure storage directories exist
        os.makedirs(self.__configuration.storage_base_path, exist_ok=True)
        os.makedirs(self.__configuration.pdf_storage_path, exist_ok=True)

    def run(self, parameters: ArXivPaperPipelineParameters) -> Graph:
        # Init graph
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

        # Generate a unique filename based on paper title and UUID
        # Clean the title to create a valid filename
        safe_title = re.sub(r'[^\w\s-]', '', paper_data["title"])
        safe_title = re.sub(r'[\s-]+', '_', safe_title).lower()
        safe_title = safe_title[:50]  # Limit length
        unique_id = str(uuid.uuid4())
        
        # Store the TTL file
        ttl_filename = f"{safe_title}_{unique_id}.ttl"
        ttl_filepath = os.path.join(self.__configuration.storage_base_path, ttl_filename)
        
        with open(ttl_filepath, 'wb') as f:
            f.write(graph.serialize(format="turtle").encode('utf-8'))
        
        print(f"Paper metadata stored at: {ttl_filepath}")
        
        # Download PDF if requested
        if parameters.download_pdf and paper_data["pdf_url"]:
            try:
                pdf_filename = f"{safe_title}_{unique_id}.pdf"
                pdf_filepath = os.path.join(self.__configuration.pdf_storage_path, pdf_filename)
                
                # Add PDF file path to graph
                graph.add((paper, ABI.localFilePath, pdf_filepath))
                
                response = requests.get(paper_data["pdf_url"], stream=True)
                response.raise_for_status()
                
                with open(pdf_filepath, 'wb') as pdf_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        pdf_file.write(chunk)
                
                print(f"PDF downloaded to: {pdf_filepath}")
                
                # Update the TTL file to include the PDF file path
                with open(ttl_filepath, 'wb') as f:
                    f.write(graph.serialize(format="turtle").encode('utf-8'))
            except Exception as e:
                print(f"Error downloading PDF: {e}")
        
        return graph

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="arxiv_paper_pipeline",
                description="Adds an ArXiv paper to the ontology and optionally downloads the PDF",
                func=lambda **kwargs: self.run(ArXivPaperPipelineParameters(**kwargs)),
                args_schema=ArXivPaperPipelineParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router."""
        @router.post("/arxiv/paper")
        def run(parameters: ArXivPaperPipelineParameters):
            return self.run(parameters).serialize(format="turtle") 
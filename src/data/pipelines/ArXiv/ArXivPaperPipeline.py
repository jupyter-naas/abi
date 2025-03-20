from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.integrations.ArXiv import ArXivIntegration
from abi.utils.Graph import ABIGraph
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src import secret
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import os
import requests
from typing import Optional
from pathlib import Path

@dataclass
class ArXivPaperPipelineConfiguration(PipelineConfiguration):
    """Configuration for ArXivPaperPipeline.
    
    Attributes:
        integration (ArXivIntegration): The ArXiv integration instance to use
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use
        pdf_storage_path (str): Path to store downloaded PDFs
    """
    integration: ArXivIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "arxiv"
    pdf_storage_path: str = "datastore/application-level/arxiv"

class ArXivPaperPipelineParameters(PipelineParameters):
    """Parameters for ArXivPaperPipeline execution.
    
    Attributes:
        paper_id (str): ArXiv ID of the paper to process
        download_pdf (bool): Whether to download the PDF. Defaults to True
    """
    paper_id: str
    download_pdf: bool = True

class ArXivPaperPipeline(Pipeline):
    """Pipeline for processing and storing ArXiv papers.
    
    This pipeline fetches paper metadata from ArXiv, converts it to RDF,
    stores it in the ontology store, and optionally downloads the PDF.
    """
    __configuration: ArXivPaperPipelineConfiguration
    
    def __init__(self, configuration: ArXivPaperPipelineConfiguration):
        self.__configuration = configuration
        self.__ARXIV = Namespace("http://arxiv.org/ontology/")
        self.__PAPER = Namespace("http://arxiv.org/paper/")
        self.__CATEGORY = Namespace("http://arxiv.org/category/")
        self.__PERSON = Namespace("http://arxiv.org/person/")
        
        # Create PDF storage directory if it doesn't exist
        os.makedirs(self.__configuration.pdf_storage_path, exist_ok=True)
        
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the pipeline tool
        """
        return [StructuredTool(
            name="store_arxiv_paper",
            description="Store a paper from ArXiv in the knowledge graph by its ID",
            func=lambda **kwargs: self.run(ArXivPaperPipelineParameters(**kwargs)),
            args_schema=ArXivPaperPipelineParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/ArXivPaperPipeline")
        def run(parameters: ArXivPaperPipelineParameters):
            return self.run(parameters).serialize(format="turtle")

    def run(self, parameters: ArXivPaperPipelineParameters) -> Graph:        
        graph = ABIGraph()
        
        # Register namespaces for better prefix representation
        graph.namespace_manager.bind("arxiv", self.__ARXIV)
        graph.namespace_manager.bind("paper", self.__PAPER)
        graph.namespace_manager.bind("category", self.__CATEGORY)
        graph.namespace_manager.bind("person", self.__PERSON)
        graph.namespace_manager.bind("dcterms", DCTERMS)
        
        # Fetch paper data from ArXiv
        paper_data = self.__configuration.integration.get_paper_by_id(parameters.paper_id)
        
        if not paper_data:
            raise ValueError(f"Paper with ID {parameters.paper_id} not found")
        
        # Create paper URI
        paper_uri = self.__PAPER[paper_data['arxiv_id']]
        
        # Add paper metadata to graph
        graph.add((paper_uri, RDF.type, self.__ARXIV.Paper))
        graph.add((paper_uri, DCTERMS.title, Literal(paper_data['title'], datatype=XSD.string)))
        graph.add((paper_uri, DCTERMS.abstract, Literal(paper_data['summary'], datatype=XSD.string)))
        graph.add((paper_uri, DCTERMS.identifier, Literal(paper_data['arxiv_id'], datatype=XSD.string)))
        graph.add((paper_uri, DCTERMS.created, Literal(paper_data['published'], datatype=XSD.dateTime)))
        graph.add((paper_uri, DCTERMS.modified, Literal(paper_data['updated'], datatype=XSD.dateTime)))
        
        if paper_data['pdf_url']:
            graph.add((paper_uri, self.__ARXIV.pdfUrl, Literal(paper_data['pdf_url'], datatype=XSD.anyURI)))
        
        # Add authors
        for i, author in enumerate(paper_data['authors']):
            # Create a simple URI for author based on position and paper ID
            author_uri = self.__PERSON[f"{paper_data['arxiv_id']}_author_{i}"]
            
            graph.add((author_uri, RDF.type, self.__ARXIV.Author))
            graph.add((author_uri, RDFS.label, Literal(author['name'], datatype=XSD.string)))
            graph.add((paper_uri, DCTERMS.creator, author_uri))
        
        # Add categories
        for category in paper_data['categories']:
            category_uri = self.__CATEGORY[category['term']]
            
            graph.add((category_uri, RDF.type, self.__ARXIV.Category))
            graph.add((category_uri, RDFS.label, Literal(category['term'], datatype=XSD.string)))
            graph.add((paper_uri, DCTERMS.subject, category_uri))
        
        # Download PDF if requested
        if parameters.download_pdf and paper_data['pdf_url']:
            pdf_path = self._download_pdf(paper_data['arxiv_id'], paper_data['pdf_url'])
            if pdf_path:
                graph.add((paper_uri, self.__ARXIV.localPdfPath, Literal(pdf_path, datatype=XSD.string)))
        
        # Store in ontology store
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        
        return graph
    
    def _download_pdf(self, paper_id: str, pdf_url: str) -> Optional[str]:
        """Download PDF for a paper and save it locally.
        
        Args:
            paper_id (str): ArXiv ID of the paper
            pdf_url (str): URL to download the PDF from
            
        Returns:
            Optional[str]: Path to the downloaded PDF or None if download failed
        """
        try:
            pdf_filename = f"{paper_id.replace('/', '_')}.pdf"
            pdf_path = os.path.join(self.__configuration.pdf_storage_path, pdf_filename)
            
            # Download if file doesn't exist yet
            if not os.path.exists(pdf_path):
                response = requests.get(pdf_url)
                response.raise_for_status()
                
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)
            
            return pdf_path
            
        except Exception as e:
            print(f"Error downloading PDF: {e}")
            return None 
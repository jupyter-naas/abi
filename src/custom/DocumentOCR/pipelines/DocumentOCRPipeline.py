from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.custom.DocumentOCR.integrations.MistralOCRIntegration import MistralOCRIntegration, MistralOCRIntegrationConfiguration
from abi.utils.Graph import ABIGraph
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, XSD
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from src import secret
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Optional, List, Dict, Any
from pathlib import Path
import os
import json
from pydantic import Field

# Define document ontology namespace
DOC = Namespace("http://abi.ai/ontologies/document#")


@dataclass
class DocumentOCRPipelineConfiguration(PipelineConfiguration):
    """Configuration for DocumentOCRPipeline.
    
    Attributes:
        integration (MistralOCRIntegration): The Mistral OCR integration instance to use
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "document_store"
        storage_path (str): Base path for storage of documents
    """
    integration: MistralOCRIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "document_store"
    storage_path: str = "/storage/datastore"


class DocumentOCRPipelineParameters(PipelineParameters):
    """Parameters for DocumentOCRPipeline execution.
    
    Attributes:
        file_path (str): Relative path to the document file to process
        output_path (Optional[str]): Relative path to save the OCR results
        include_image_base64 (bool): Whether to include image data in the results
        use_document_understanding (bool): Whether to use document understanding with LLM
        query (Optional[str]): Question to ask about the document if using document understanding
    """
    file_path: str = Field(..., description="Relative path to the document file to process")
    output_path: Optional[str] = Field(None, description="Relative path to save the OCR results")
    include_image_base64: bool = Field(False, description="Whether to include image data in the results")
    use_document_understanding: bool = Field(False, description="Whether to use document understanding with LLM")
    query: Optional[str] = Field(None, description="Question to ask about the document if using document understanding")


class BatchDocumentOCRPipelineParameters(PipelineParameters):
    """Parameters for batch document OCR processing.
    
    Attributes:
        directory_path (str): Relative path to directory containing files to process
        output_directory (Optional[str]): Directory to save OCR results
    """
    directory_path: str = Field(..., description="Relative path to directory containing files to process")
    output_directory: Optional[str] = Field(None, description="Directory to save OCR results")


class DocumentOCRPipeline(Pipeline):
    """Pipeline for processing documents with OCR capabilities.
    
    This pipeline uses Mistral OCR to extract text and structured content from documents.
    It can handle PDFs and images, and can also use document understanding to answer
    questions about the content.
    """
    
    __configuration: DocumentOCRPipelineConfiguration
    
    def __init__(self, configuration: DocumentOCRPipelineConfiguration):
        """Initialize the document OCR pipeline with configuration."""
        self.__configuration = configuration
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the pipeline tools
        """
        return [
            StructuredTool(
                name="process_document_ocr",
                description="Process a document file with OCR to extract text and structure",
                func=lambda **kwargs: self.run(DocumentOCRPipelineParameters(**kwargs)),
                args_schema=DocumentOCRPipelineParameters
            ),
            StructuredTool(
                name="batch_process_documents_ocr",
                description="Process multiple document files in a directory with OCR",
                func=lambda **kwargs: self.run_batch(BatchDocumentOCRPipelineParameters(**kwargs)),
                args_schema=BatchDocumentOCRPipelineParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/document/ocr")
        def run_document_ocr(parameters: DocumentOCRPipelineParameters):
            return self.run(parameters).serialize(format="turtle")
        
        @router.post("/document/ocr/batch")
        def run_batch_document_ocr(parameters: BatchDocumentOCRPipelineParameters):
            return self.run_batch(parameters).serialize(format="turtle")

    def run(self, parameters: DocumentOCRPipelineParameters) -> Graph:
        """Run the document OCR pipeline with the given parameters.
        
        Args:
            parameters (DocumentOCRPipelineParameters): Parameters for the pipeline execution
            
        Returns:
            Graph: RDF graph containing the OCR results and metadata
        """
        graph = ABIGraph()
        
        # Add namespaces
        graph.bind("doc", DOC)
        
        # Create document node
        document_id = Path(parameters.file_path).stem
        document_uri = URIRef(f"http://abi.ai/document/{document_id}")
        
        # Add document type
        graph.add((document_uri, RDF.type, DOC.Document))
        
        # Add document file path
        graph.add((document_uri, DOC.filePath, Literal(parameters.file_path)))
        
        if parameters.use_document_understanding and parameters.query:
            # Use document understanding to get answers
            understanding_result = self.__configuration.integration.document_understanding(
                file_path=parameters.file_path,
                query=parameters.query
            )
            
            # Add understanding result to graph
            query_uri = URIRef(f"http://abi.ai/document/{document_id}/query")
            graph.add((query_uri, RDF.type, DOC.Query))
            graph.add((query_uri, DOC.queryText, Literal(parameters.query)))
            graph.add((query_uri, DOC.answer, Literal(understanding_result)))
            graph.add((document_uri, DOC.hasQuery, query_uri))
        else:
            # Process the document with OCR
            ocr_result = self.__configuration.integration.process_local_file(
                file_path=parameters.file_path,
                output_path=parameters.output_path,
                include_image_base64=parameters.include_image_base64
            )
            
            # Add OCR result to graph
            ocr_uri = URIRef(f"http://abi.ai/document/{document_id}/ocr")
            graph.add((ocr_uri, RDF.type, DOC.OCRResult))
            
            # Add text content
            if hasattr(ocr_result, 'text'):
                graph.add((ocr_uri, DOC.textContent, Literal(ocr_result.text)))
            
            # Add JSON representation if available
            if ocr_result:
                # Convert to string for storage in graph
                ocr_json = str(ocr_result)
                graph.add((ocr_uri, DOC.jsonContent, Literal(ocr_json)))
            
            # Link OCR result to document
            graph.add((document_uri, DOC.hasOCRResult, ocr_uri))
            
            # Add output path if specified
            if parameters.output_path:
                graph.add((ocr_uri, DOC.outputPath, Literal(parameters.output_path)))
        
        # Store the graph in the ontology store
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        
        return graph
    
    def run_batch(self, parameters: BatchDocumentOCRPipelineParameters) -> Graph:
        """Run the document OCR pipeline in batch mode for multiple files.
        
        Args:
            parameters (BatchDocumentOCRPipelineParameters): Parameters for batch processing
            
        Returns:
            Graph: RDF graph containing the OCR results and metadata for all processed files
        """
        graph = ABIGraph()
        
        # Add namespaces
        graph.bind("doc", DOC)
        
        # Process batch of files
        batch_results = self.__configuration.integration.batch_process_files(
            directory_path=parameters.directory_path,
            output_directory=parameters.output_directory
        )
        
        # Add batch processing information
        batch_uri = URIRef(f"http://abi.ai/document/batch/{Path(parameters.directory_path).name}")
        graph.add((batch_uri, RDF.type, DOC.BatchProcessing))
        graph.add((batch_uri, DOC.directoryPath, Literal(parameters.directory_path)))
        
        if parameters.output_directory:
            graph.add((batch_uri, DOC.outputDirectory, Literal(parameters.output_directory)))
        
        # Add results for each file
        for filename, result in batch_results.items():
            # Create document node
            document_id = Path(filename).stem
            document_uri = URIRef(f"http://abi.ai/document/{document_id}")
            
            # Add document type and file path
            graph.add((document_uri, RDF.type, DOC.Document))
            graph.add((document_uri, DOC.filePath, Literal(os.path.join(parameters.directory_path, filename))))
            
            # Link document to batch
            graph.add((batch_uri, DOC.hasDocument, document_uri))
            
            # Add OCR result if successful
            if isinstance(result, str) and result.startswith("Error:"):
                # Add error information
                graph.add((document_uri, DOC.processingError, Literal(result)))
            else:
                # Add OCR result
                ocr_uri = URIRef(f"http://abi.ai/document/{document_id}/ocr")
                graph.add((ocr_uri, RDF.type, DOC.OCRResult))
                
                # Add text content if available
                if hasattr(result, 'text'):
                    graph.add((ocr_uri, DOC.textContent, Literal(result.text)))
                
                # Add JSON representation
                ocr_json = str(result)
                graph.add((ocr_uri, DOC.jsonContent, Literal(ocr_json)))
                
                # Link OCR result to document
                graph.add((document_uri, DOC.hasOCRResult, ocr_uri))
        
        # Store the graph in the ontology store
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        
        return graph 
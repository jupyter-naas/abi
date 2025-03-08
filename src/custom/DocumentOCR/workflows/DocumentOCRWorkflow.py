from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.custom.DocumentOCR.integrations.MistralOCRIntegration import MistralOCRIntegration, MistralOCRIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import os
from pathlib import Path

@dataclass
class DocumentOCRWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for DocumentOCRWorkflow.
    
    Attributes:
        integration_config (MistralOCRIntegrationConfiguration): Configuration for the Mistral OCR integration
        storage_path (str): Base path for storage of documents
    """
    integration_config: MistralOCRIntegrationConfiguration
    storage_path: str = "/storage/datastore"


class ProcessDocumentParameters(WorkflowParameters):
    """Parameters for document processing execution.
    
    Attributes:
        file_path (str): Path to the document file to process
        output_path (Optional[str]): Path to save the OCR results. If not provided, defaults to a markdown file with the same name as the input file.
        include_image_base64 (bool): Whether to include image data in the results
    """
    file_path: str = Field(..., description="Path to the document file to process")
    output_path: Optional[str] = Field(None, description="Path to save the OCR results. If not provided, defaults to a markdown file with the same name as the input file.")
    include_image_base64: bool = Field(False, description="Whether to include image data in the results")


class DocumentUnderstandingParameters(WorkflowParameters):
    """Parameters for document understanding execution.
    
    Attributes:
        file_path (str): Path to the document file to process
        query (str): Question to ask about the document
        model (str): Model to use for understanding
    """
    file_path: str = Field(..., description="Path to the document file to process")
    query: str = Field(..., description="Question to ask about the document")
    model: str = Field("mistral-small-latest", description="Model to use for understanding")


class BatchProcessDocumentsParameters(WorkflowParameters):
    """Parameters for batch document processing.
    
    Attributes:
        directory_path (str): Path to directory containing files to process
        output_directory (Optional[str]): Directory to save OCR results
    """
    directory_path: str = Field(..., description="Path to directory containing files to process")
    output_directory: Optional[str] = Field(None, description="Directory to save OCR results")


class DocumentOCRWorkflow(Workflow):
    """Workflow for processing documents with OCR and document understanding.
    
    This workflow provides methods to extract text and structured content from documents
    using Mistral's OCR capabilities. It can process PDF documents and images, and can
    also answer questions about the document content using document understanding.
    """
    
    __configuration: DocumentOCRWorkflowConfiguration
    __integration: MistralOCRIntegration
    
    def __init__(self, configuration: DocumentOCRWorkflowConfiguration):
        """Initialize document OCR workflow with configuration."""
        self.__configuration = configuration
        self.__integration = MistralOCRIntegration(self.__configuration.integration_config)
    
    def __normalize_path(self, path: str) -> str:
        """Normalize a path to avoid duplicating the storage path.
        
        Args:
            path (str): The path to normalize
            
        Returns:
            str: The normalized path
        """
        if not path:
            return path
            
        # If already absolute, return as is
        if os.path.isabs(path):
            return path
            
        # Check if the path already starts with the storage path prefix
        storage_path = self.__configuration.storage_path
        if path.startswith(storage_path) or path.startswith(storage_path.lstrip('/')):
            # Remove the leading slash if present for consistency in path joining
            clean_storage_path = storage_path.lstrip('/')
            # Strip the storage path from the beginning if it's duplicated
            if path.startswith(clean_storage_path):
                path = path[len(clean_storage_path):]
                if path.startswith('/'):
                    path = path[1:]
        
        # Now join with the storage path
        return os.path.join(self.__configuration.storage_path, path)
    
    def process_document(self, parameters: ProcessDocumentParameters) -> Dict[str, Any]:
        """Process a document with OCR to extract text and structure.
        
        Args:
            parameters (ProcessDocumentParameters): Parameters for document processing
            
        Returns:
            Dict[str, Any]: OCR processing results
        """
        logger.info(f"Processing document: {parameters.file_path}")
        
        try:
            # If no output path is specified, create a default one with markdown extension
            output_path = parameters.output_path
            if not output_path:
                input_path = Path(parameters.file_path)
                output_path = str(input_path.parent / f"{input_path.stem}.md")
                logger.info(f"No output path specified. Defaulting to: {output_path}")
            
            # Process the document
            result = self.__integration.process_local_file(
                file_path=parameters.file_path,
                output_path=output_path,
                include_image_base64=parameters.include_image_base64
            )
            
            # Create response
            response = {
                "status": "success",
                "file_processed": parameters.file_path,
                "result": "OCR processing completed successfully",
                "output_location": output_path
            }
            
            # Add content if available
            if hasattr(result, 'text'):
                response["text_content"] = result.text
            
            return response
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return {
                "status": "error",
                "file": parameters.file_path,
                "error": str(e)
            }
    
    def document_understanding(self, parameters: DocumentUnderstandingParameters) -> Dict[str, Any]:
        """Process a document and get answers to questions about its content.
        
        Args:
            parameters (DocumentUnderstandingParameters): Parameters for document understanding
            
        Returns:
            Dict[str, Any]: Document understanding results
        """
        logger.info(f"Document understanding for: {parameters.file_path}, query: {parameters.query}")
        
        try:
            # Process the document with understanding
            result = self.__integration.document_understanding(
                file_path=parameters.file_path,
                query=parameters.query,
                model=parameters.model
            )
            
            return {
                "status": "success",
                "file": parameters.file_path,
                "query": parameters.query,
                "answer": result
            }
        except Exception as e:
            logger.error(f"Error in document understanding: {e}")
            return {
                "status": "error",
                "file": parameters.file_path,
                "query": parameters.query,
                "error": str(e)
            }
    
    def batch_process_documents(self, parameters: BatchProcessDocumentsParameters) -> Dict[str, Any]:
        """Process multiple documents in a directory with OCR.
        
        Args:
            parameters (BatchProcessDocumentsParameters): Parameters for batch processing
            
        Returns:
            Dict[str, Any]: Batch processing results
        """
        logger.info(f"Batch processing documents in: {parameters.directory_path}")
        
        try:
            # Process the documents
            results = self.__integration.batch_process_files(
                directory_path=parameters.directory_path,
                output_directory=parameters.output_directory
            )
            
            # Create summary of processed files
            successful_files = []
            failed_files = []
            
            for filename, result in results.items():
                if isinstance(result, str) and result.startswith("Error:"):
                    failed_files.append({
                        "file": filename,
                        "error": result
                    })
                else:
                    successful_files.append(filename)
            
            return {
                "status": "completed",
                "directory_processed": parameters.directory_path,
                "total_files": len(results),
                "successful_files": len(successful_files),
                "failed_files": len(failed_files),
                "failures": failed_files,
                "output_directory": parameters.output_directory
            }
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            return {
                "status": "error",
                "directory": parameters.directory_path,
                "error": str(e)
            }
    
    def run(self, parameters: ProcessDocumentParameters) -> Dict[str, Any]:
        """Run the document OCR workflow with the given parameters.
        
        This is the main entry point for the workflow.
        
        Args:
            parameters (ProcessDocumentParameters): Parameters for document processing
            
        Returns:
            Dict[str, Any]: OCR processing results
        """
        return self.process_document(parameters)
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tools
        """
        return [
            StructuredTool(
                name="document_ocr_process",
                description="Process a document with OCR to extract text and structure. Results are saved as a markdown file by default.",
                func=lambda **kwargs: self.process_document(ProcessDocumentParameters(**kwargs)),
                args_schema=ProcessDocumentParameters
            ),
            StructuredTool(
                name="document_understanding",
                description="Process a document and get answers to questions about its content",
                func=lambda **kwargs: self.document_understanding(DocumentUnderstandingParameters(**kwargs)),
                args_schema=DocumentUnderstandingParameters
            ),
            StructuredTool(
                name="document_ocr_batch_process",
                description="Process multiple documents in a directory with OCR",
                func=lambda **kwargs: self.batch_process_documents(BatchProcessDocumentsParameters(**kwargs)),
                args_schema=BatchProcessDocumentsParameters
            )
        ]
    
    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/document/ocr/process")
        def process_document(parameters: ProcessDocumentParameters):
            return self.process_document(parameters)
        
        @router.post("/document/understanding")
        def document_understanding(parameters: DocumentUnderstandingParameters):
            return self.document_understanding(parameters)
        
        @router.post("/document/ocr/batch")
        def batch_process_documents(parameters: BatchProcessDocumentsParameters):
            return self.batch_process_documents(parameters) 
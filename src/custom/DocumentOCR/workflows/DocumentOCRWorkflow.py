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


class ExtractTablesParameters(WorkflowParameters):
    """Parameters for extracting tables from a document.
    
    Attributes:
        file_path (str): Path to the document file containing tables
        output_directory (Optional[str]): Directory to save CSV files, defaults to same directory as input file
        consolidate_tables (bool): Whether to consolidate tables with the same headers
    """
    file_path: str = Field(..., description="Path to the document file containing tables")
    output_directory: Optional[str] = Field(None, description="Directory to save CSV files, defaults to same directory as input file")
    consolidate_tables: bool = Field(True, description="Whether to consolidate tables with the same headers")


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
                
            # Check for CSV files that were exported from tables
            base_dir = os.path.dirname(self.__normalize_path(output_path))
            base_filename = os.path.splitext(os.path.basename(output_path))[0]
            csv_files = [f for f in os.listdir(base_dir) if f.startswith(base_filename) and f.endswith('.csv')]
            
            if csv_files:
                response["exported_csv_files"] = [os.path.join(base_dir, f) for f in csv_files]
                logger.info(f"Exported {len(csv_files)} tables as CSV files")
            
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
    
    def extract_tables(self, parameters: ExtractTablesParameters) -> Dict[str, Any]:
        """Extract tables from a document and save them as CSV files.
        
        This method uses the DocumentOCR pipeline to extract tables from markdown files
        and save them as CSV files. If consolidate_tables is True, tables with the same 
        headers will be consolidated into a single CSV file.
        
        Args:
            parameters (ExtractTablesParameters): Parameters for table extraction
            
        Returns:
            Dict[str, Any]: Result of table extraction
        """
        from src.custom.DocumentOCR.pipelines.DocumentOCRPipeline import TableExtractionParameters, DocumentOCRPipeline, DocumentOCRPipelineConfiguration
        
        # Configure the OCR pipeline
        pipeline_config = DocumentOCRPipelineConfiguration(
            integration=self.__integration,
            ontology_store=None,  # Not needed for table extraction
            storage_path=self.__configuration.storage_path
        )
        
        # Create pipeline
        pipeline = DocumentOCRPipeline(pipeline_config)
        
        # Create pipeline parameters
        pipeline_params = TableExtractionParameters(
            file_path=parameters.file_path,
            output_directory=parameters.output_directory,
            consolidate_tables=parameters.consolidate_tables
        )
        
        # Run the pipeline
        result = pipeline.extract_tables(pipeline_params)
        
        return result
    
    def run(self, parameters: ProcessDocumentParameters) -> Dict[str, Any]:
        """Run document processing.
        
        Args:
            parameters (ProcessDocumentParameters): Parameters for document processing
            
        Returns:
            Dict[str, Any]: Processing results
        """
        return self.process_document(parameters)
    
    def fix_ocr_file(self, file_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Fix an existing OCR output file that contains raw OCR response objects.
        
        This method extracts the actual markdown content from files that were incorrectly
        generated and converts them to proper markdown.
        
        Args:
            file_path (str): Path to the OCR file to fix
            output_path (Optional[str]): Path to save the fixed result. If not provided,
                                        overwrites the original file.
            
        Returns:
            Dict[str, Any]: Result of the operation
        """
        try:
            # Normalize paths
            abs_file_path = self.__normalize_path(file_path)
            
            # If no output path is specified, overwrite the original file
            if not output_path:
                output_path = file_path
            
            abs_output_path = self.__normalize_path(output_path)
            
            # Check if file exists
            if not os.path.exists(abs_file_path):
                return {"status": "error", "message": f"File not found: {file_path}"}
            
            # Read the file content
            with open(abs_file_path, 'r') as f:
                content = f.read()
            
            # Check if this is an OCR result file with pages/markdown structure
            if "pages=[" in content and "markdown='" in content:
                # Extract markdown content
                markdown_content = ""
                
                # Add title from the original filename
                if os.path.basename(abs_file_path).endswith('.pdf.md'):
                    title = os.path.basename(abs_file_path)[:-7]  # Remove .pdf.md
                else:
                    title = os.path.basename(abs_file_path)
                
                markdown_content += f"# {title}\n\n"
                
                # Extract all markdown sections
                parts = content.split("markdown='")
                for i in range(1, len(parts)):
                    end_index = parts[i].find("'")
                    if end_index != -1:
                        extracted_markdown = parts[i][:end_index]
                        markdown_content += extracted_markdown
                        markdown_content += "\n\n"
                
                # Write the extracted markdown content
                with open(abs_output_path, 'w') as f:
                    f.write(markdown_content)
                
                return {
                    "status": "success",
                    "file_processed": file_path,
                    "result": "OCR file fixed successfully",
                    "output_location": output_path
                }
            else:
                return {
                    "status": "info",
                    "message": "File does not appear to be a raw OCR result. No changes made."
                }
                
        except Exception as e:
            logger.error(f"Error fixing OCR file: {e}")
            return {
                "status": "error",
                "message": f"Failed to fix OCR file: {str(e)}"
            }
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tools
        """
        # Create document processing tool
        process_tool = StructuredTool(
            name="document_ocr_process",
            description="Process a document with OCR to extract text and structure",
            func=lambda **kwargs: self.process_document(ProcessDocumentParameters(**kwargs)),
            args_schema=ProcessDocumentParameters
        )
        
        # Create document understanding tool
        understanding_tool = StructuredTool(
            name="document_ocr_understanding",
            description="Answer questions about a document using OCR and document understanding",
            func=lambda **kwargs: self.document_understanding(DocumentUnderstandingParameters(**kwargs)),
            args_schema=DocumentUnderstandingParameters
        )
        
        # Create batch processing tool
        batch_tool = StructuredTool(
            name="document_ocr_batch_process",
            description="Process multiple documents with OCR",
            func=lambda **kwargs: self.batch_process_documents(BatchProcessDocumentsParameters(**kwargs)),
            args_schema=BatchProcessDocumentsParameters
        )
        
        # Create fix OCR file tool
        class FixOCRFileParameters(BaseModel):
            """Parameters for fixing OCR file format."""
            file_path: str = Field(..., description="Path to the OCR file to fix")
            output_path: Optional[str] = Field(None, description="Path to save the fixed result. If not provided, overwrites the original file.")
        
        fix_tool = StructuredTool(
            name="document_ocr_fix_file",
            description="Fix an existing OCR output file that contains raw OCR response objects",
            func=lambda **kwargs: self.fix_ocr_file(**kwargs),
            args_schema=FixOCRFileParameters
        )
        
        # Create extract tables tool
        extract_tables_tool = StructuredTool(
            name="document_ocr_extract_tables",
            description="Extract tables from a document and save them as CSV files",
            func=lambda **kwargs: self.extract_tables(ExtractTablesParameters(**kwargs)),
            args_schema=ExtractTablesParameters
        )
        
        return [process_tool, understanding_tool, batch_tool, fix_tool, extract_tables_tool]
    
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
        
        # Add API endpoint for fixing OCR files
        class FixOCRFileParameters(BaseModel):
            """Parameters for fixing OCR file format."""
            file_path: str = Field(..., description="Path to the OCR file to fix")
            output_path: Optional[str] = Field(None, description="Path to save the fixed result. If not provided, overwrites the original file.")
            
        @router.post("/document/ocr/fix")
        def fix_ocr_file(parameters: FixOCRFileParameters):
            return self.fix_ocr_file(**parameters.dict())
        
        # Add API endpoint for extracting tables
        @router.post("/document/ocr/extract-tables")
        def extract_tables(parameters: ExtractTablesParameters):
            return self.extract_tables(parameters) 
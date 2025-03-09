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
import shutil

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


class TableExtractionParameters(PipelineParameters):
    """Parameters for table extraction from documents.
    
    Attributes:
        file_path (str): Path to the markdown file containing tables
        output_directory (Optional[str]): Directory to save CSV files, defaults to same directory as input file
        consolidate_tables (bool): Whether to consolidate tables with the same headers
    """
    file_path: str = Field(..., description="Path to the markdown file containing tables")
    output_directory: Optional[str] = Field(None, description="Directory to save CSV files, defaults to same directory as input file")
    consolidate_tables: bool = Field(True, description="Whether to consolidate tables with the same headers")


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
            ),
            StructuredTool(
                name="extract_tables_from_document",
                description="Extract tables from a document and save them as CSV files",
                func=lambda **kwargs: self.extract_tables(TableExtractionParameters(**kwargs)),
                args_schema=TableExtractionParameters
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
        
        @router.post("/document/extract-tables")
        def extract_tables(parameters: TableExtractionParameters):
            return self.extract_tables(parameters)

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
    
    def extract_tables(self, parameters: TableExtractionParameters) -> Dict[str, Any]:
        """Extract tables from a document and save them as CSV files.
        
        If consolidate_tables is True, tables with the same headers will be
        consolidated into a single CSV file with suffix "_consolidated".
        
        Args:
            parameters (TableExtractionParameters): Parameters for table extraction
            
        Returns:
            Dict[str, Any]: Result of table extraction including paths to CSV files
        """
        import re
        import csv
        
        try:
            # Normalize the file path
            file_path = os.path.join(self.__configuration.storage_path, parameters.file_path)
            
            # Check if file exists
            if not os.path.exists(file_path):
                return {
                    "status": "error",
                    "message": f"File not found: {parameters.file_path}"
                }
            
            # Determine base output directory
            if parameters.output_directory:
                base_output_dir = os.path.join(self.__configuration.storage_path, parameters.output_directory)
            else:
                base_output_dir = os.path.dirname(file_path)
                
            # Get the base filename without extension for creating the OCR_ folder
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            file_extension = os.path.splitext(os.path.basename(file_path))[1]
            
            # Create a dedicated output folder with prefix OCR_
            output_dir = os.path.join(base_output_dir, f"OCR_{base_filename}")
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Read the markdown content
            with open(file_path, 'r') as f:
                markdown_content = f.read()
            
            # Copy the original markdown file to the OCR_ folder
            markdown_dest_path = os.path.join(output_dir, f"{base_filename}{file_extension}")
            shutil.copy2(file_path, markdown_dest_path)
            
            # Regular expression to find tables in markdown
            table_pattern = r'(?:#+ *(.*?)\s*\n\n?)?(?:\|.*\|\n\|[-:\| ]+\|\n)(\|.*\|\n)+'
            
            # Find all tables
            tables_found = re.finditer(table_pattern, markdown_content, re.MULTILINE)
            
            csv_files = []
            table_counter = 1
            
            # Store tables by headers for consolidation
            tables_by_headers = {}
            
            # Process each table found
            for table_match in tables_found:
                # Try to get the table name (heading before the table)
                table_name = table_match.group(1)
                if not table_name:
                    # Use the document name and table number if no name is found
                    table_name = f"Table_{table_counter}"
                else:
                    # Clean up the table name for use as a filename
                    table_name = re.sub(r'[^\w\s-]', '', table_name).strip().replace(' ', '_')
                    
                # Ensure we have a valid filename
                if not table_name:
                    table_name = f"Table_{table_counter}"
                
                # Extract table rows
                table_content = table_match.group(0)
                rows = []
                
                # Process each row of the table
                for line in table_content.strip().split('\n'):
                    if line.startswith('|') and not all(c in '| -:' for c in line):
                        # Parse cells, removing leading/trailing | and whitespace
                        cells = [cell.strip() for cell in line.split('|')[1:-1]]
                        rows.append(cells)
                
                if len(rows) > 1:  # Ensure we have header and at least one data row
                    # Create CSV file in the OCR_ folder
                    csv_file_path = os.path.join(output_dir, f"{table_name}.csv")
                    
                    try:
                        with open(csv_file_path, 'w', newline='') as csv_file:
                            writer = csv.writer(csv_file)
                            # Write all rows to the CSV
                            for row in rows:
                                writer.writerow(row)
                        
                        csv_files.append(csv_file_path)
                        
                        # Store table for potential consolidation if requested
                        if parameters.consolidate_tables:
                            # Use header row as a key (tuple for immutability)
                            header_tuple = tuple(rows[0])
                            if header_tuple not in tables_by_headers:
                                tables_by_headers[header_tuple] = []
                            tables_by_headers[header_tuple].append(rows[1:])  # Store data rows only
                            
                    except Exception as e:
                        return {
                            "status": "error",
                            "message": f"Error saving CSV file: {str(e)}"
                        }
                
                table_counter += 1
            
            # Create consolidated CSVs for tables with the same headers if requested
            consolidated_files = []
            if parameters.consolidate_tables:
                for header_tuple, table_data_list in tables_by_headers.items():
                    if len(table_data_list) > 1:  # Only consolidate if we have multiple tables with same headers
                        # Create a consolidated table with all data rows
                        header = list(header_tuple)
                        all_data_rows = []
                        for data_rows in table_data_list:
                            all_data_rows.extend(data_rows)
                        
                        # Generate a name based on the headers
                        header_name = "_".join([h.replace(' ', '_') for h in header if h])[:30]  # Limit length
                        consolidated_csv_path = os.path.join(output_dir, f"{header_name}_consolidated.csv")
                        
                        try:
                            with open(consolidated_csv_path, 'w', newline='') as csv_file:
                                writer = csv.writer(csv_file)
                                # Write the header
                                writer.writerow(header)
                                # Write all data rows
                                for row in all_data_rows:
                                    writer.writerow(row)
                            
                            consolidated_files.append(consolidated_csv_path)
                        except Exception as e:
                            return {
                                "status": "error",
                                "message": f"Error saving consolidated CSV file: {str(e)}"
                            }
            
            # Create response
            response = {
                "status": "success",
                "file_processed": parameters.file_path,
                "tables_found": table_counter - 1,
                "output_directory": os.path.relpath(output_dir, self.__configuration.storage_path),
                "markdown_file": os.path.relpath(markdown_dest_path, self.__configuration.storage_path),
                "csv_files": [os.path.relpath(path, self.__configuration.storage_path) for path in csv_files]
            }
            
            if consolidated_files:
                response["consolidated_csv_files"] = [os.path.relpath(path, self.__configuration.storage_path) for path in consolidated_files]
                
            return response
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error extracting tables: {str(e)}"
            } 
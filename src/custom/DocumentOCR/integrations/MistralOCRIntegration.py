from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Any, BinaryIO
from mistralai import Mistral
from src import config, secret
from abi import logger
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import os
import base64
from pathlib import Path
import json

LOGO_URL = "https://logo.clearbit.com/mistral.ai"

@dataclass
class MistralOCRIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Mistral OCR integration.
    
    Attributes:
        api_key (str): Mistral API key for authentication
        storage_path (str): Path where documents are stored and processed results will be saved
    """
    api_key: str
    storage_path: str = "/storage/datastore"

class MistralOCRIntegration(Integration):
    """Mistral OCR integration class for document processing and understanding.
    
    This class provides methods to extract text and structured content from 
    documents using Mistral's OCR capabilities. It can process PDF documents
    and images, maintaining document structure and formatting.
    
    Attributes:
        __configuration (MistralOCRIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = MistralOCRIntegrationConfiguration(
        ...     api_key="your-api-key",
        ...     storage_path="/storage/datastore"
        ... )
        >>> integration = MistralOCRIntegration(config)
    """

    __configuration: MistralOCRIntegrationConfiguration

    def __init__(self, configuration: MistralOCRIntegrationConfiguration):
        """Initialize Mistral OCR client with configuration."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__client = Mistral(api_key=self.__configuration.api_key)
    
    def process_pdf_from_url(self, document_url: str, include_image_base64: bool = False) -> Dict:
        """Process a PDF document from a URL using Mistral OCR.
        
        Args:
            document_url (str): URL of the PDF document to process
            include_image_base64 (bool): Whether to include image base64 data in the response
            
        Returns:
            Dict: OCR processing results including extracted text and document structure
        """
        try:
            ocr_response = self.__client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": document_url
                },
                include_image_base64=include_image_base64
            )
            return ocr_response
        except Exception as e:
            logger.error(f"Error processing PDF from URL: {e}")
            raise IntegrationConnectionError(f"Failed to process PDF: {e}")
    
    def process_local_file(
        self, 
        file_path: str, 
        output_path: Optional[str] = None,
        include_image_base64: bool = False
    ) -> Dict:
        """Process a local PDF or image file using Mistral OCR.
        
        Args:
            file_path (str): Path to the local file (PDF or image)
            output_path (Optional[str]): Path to save the OCR results
            include_image_base64 (bool): Whether to include image base64 data in the response
            
        Returns:
            Dict: OCR processing results including extracted text and document structure
        """
        try:
            # Get absolute file path
            abs_file_path = self.__normalize_path(file_path)
            
            # Check if file exists
            if not os.path.exists(abs_file_path):
                raise FileNotFoundError(f"File not found: {abs_file_path}")
            
            # Determine file type
            file_extension = os.path.splitext(abs_file_path)[1].lower()
            
            # Process file based on type
            if file_extension in ['.pdf']:
                # Upload PDF file
                with open(abs_file_path, "rb") as file:
                    uploaded_file = self.__client.files.upload(
                        file={
                            "file_name": os.path.basename(abs_file_path),
                            "content": file,
                        },
                        purpose="ocr"
                    )
                
                # Get signed URL
                signed_url = self.__client.files.get_signed_url(file_id=uploaded_file.id)
                
                # Process the uploaded file
                ocr_response = self.__client.ocr.process(
                    model="mistral-ocr-latest",
                    document={
                        "type": "document_url",
                        "document_url": signed_url.url,
                    },
                    include_image_base64=include_image_base64
                )
            elif file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                # Process image file
                base64_image = self.__encode_image(abs_file_path)
                
                ocr_response = self.__client.ocr.process(
                    model="mistral-ocr-latest",
                    document={
                        "type": "image_url",
                        "image_url": f"data:image/{file_extension[1:]};base64,{base64_image}"
                    },
                    include_image_base64=include_image_base64
                )
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            # Save results if output path is provided
            if output_path:
                abs_output_path = self.__normalize_path(output_path)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
                
                # Check if output should be formatted as markdown
                output_ext = os.path.splitext(abs_output_path)[1].lower()
                if output_ext == '.md':
                    # Format as markdown
                    with open(abs_output_path, 'w') as f:
                        # Add the title as first-level heading
                        f.write(f"# {os.path.basename(abs_file_path)}\n\n")
                        
                        # Add document text as content
                        if hasattr(ocr_response, 'text'):
                            f.write(ocr_response.text)
                        elif isinstance(ocr_response, dict) and 'text' in ocr_response:
                            f.write(ocr_response['text'])
                        else:
                            f.write(str(ocr_response))
                else:
                    # Write results to file as is
                    with open(abs_output_path, 'w') as f:
                        if isinstance(ocr_response, dict):
                            json.dump(ocr_response, f, indent=2)
                        else:
                            f.write(str(ocr_response))
            
            return ocr_response
        except Exception as e:
            logger.error(f"Error processing local file: {e}")
            raise IntegrationConnectionError(f"Failed to process file: {e}")
    
    def __encode_image(self, image_path: str) -> str:
        """Encode an image to base64.
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            str: Base64 encoded image data
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            raise IntegrationConnectionError(f"Failed to encode image: {e}")
    
    def document_understanding(
        self, 
        file_path: str, 
        query: str, 
        model: str = "mistral-small-latest"
    ) -> str:
        """Process a document and get answers to questions about its content.
        
        Args:
            file_path (str): Path to the local file
            query (str): Question to ask about the document
            model (str): Mistral model to use for understanding
            
        Returns:
            str: Answer to the question based on document content
        """
        try:
            # Get absolute file path
            abs_file_path = self.__normalize_path(file_path)
            
            # Check if file exists
            if not os.path.exists(abs_file_path):
                raise FileNotFoundError(f"File not found: {abs_file_path}")
            
            # Upload and process the file
            with open(abs_file_path, "rb") as file:
                uploaded_file = self.__client.files.upload(
                    file={
                        "file_name": os.path.basename(abs_file_path),
                        "content": file,
                    },
                    purpose="ocr"
                )
            
            # Get signed URL
            signed_url = self.__client.files.get_signed_url(file_id=uploaded_file.id)
            
            # Create messages for chat
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": query
                        },
                        {
                            "type": "document_url",
                            "document_url": signed_url.url
                        }
                    ]
                }
            ]
            
            # Get chat response
            chat_response = self.__client.chat.complete(
                model=model,
                messages=messages
            )
            
            return chat_response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in document understanding: {e}")
            raise IntegrationConnectionError(f"Failed in document understanding: {e}")
    
    def batch_process_files(self, directory_path: str, output_directory: str = None) -> Dict[str, Any]:
        """Process multiple files in a directory using Mistral OCR.
        
        Args:
            directory_path (str): Path to directory containing files to process
            output_directory (str): Directory to save OCR results
            
        Returns:
            Dict[str, Any]: Dictionary mapping filenames to their OCR results
        """
        try:
            # Get absolute directory path
            abs_dir_path = self.__normalize_path(directory_path)
            
            # Set output directory
            abs_output_dir = output_directory
            if output_directory:
                abs_output_dir = self.__normalize_path(output_directory)
            
            # Create output directory if it doesn't exist
            if abs_output_dir:
                os.makedirs(abs_output_dir, exist_ok=True)
            
            # Process each file in the directory
            results = {}
            for filename in os.listdir(abs_dir_path):
                file_path = os.path.join(abs_dir_path, filename)
                
                # Skip directories
                if os.path.isdir(file_path):
                    continue
                
                # Process only PDFs and images
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                    continue
                
                # Process file
                output_path = None
                if abs_output_dir:
                    output_filename = f"{os.path.splitext(filename)[0]}_ocr_result.txt"
                    output_path = os.path.join(abs_output_dir, output_filename)
                
                try:
                    result = self.process_local_file(file_path, output_path)
                    results[filename] = result
                except Exception as e:
                    results[filename] = f"Error: {str(e)}"
            
            return results
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            raise IntegrationConnectionError(f"Failed in batch processing: {e}")

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

def as_tools(configuration: MistralOCRIntegrationConfiguration):
    """Convert Mistral OCR integration into LangChain tools."""
    integration = MistralOCRIntegration(configuration)

    class ProcessPDFFromURLSchema(BaseModel):
        document_url: str = Field(description="URL of the PDF document to process")
        include_image_base64: bool = Field(
            description="Whether to include image base64 data in the response",
            default=False
        )

    class ProcessLocalFileSchema(BaseModel):
        file_path: str = Field(description="Path to the local file (PDF or image)")
        output_path: Optional[str] = Field(
            description="Path to save the OCR results",
            default=None
        )
        include_image_base64: bool = Field(
            description="Whether to include image base64 data in the response",
            default=False
        )

    class DocumentUnderstandingSchema(BaseModel):
        file_path: str = Field(description="Path to the local file")
        query: str = Field(description="Question to ask about the document")
        model: str = Field(
            description="Mistral model to use for understanding",
            default="mistral-small-latest"
        )

    class BatchProcessFilesSchema(BaseModel):
        directory_path: str = Field(description="Path to directory containing files to process")
        output_directory: Optional[str] = Field(
            description="Directory to save OCR results",
            default=None
        )

    return [
        StructuredTool(
            name="mistral_ocr_process_pdf_from_url",
            description="Process a PDF document from a URL using Mistral OCR",
            func=lambda **kwargs: integration.process_pdf_from_url(**kwargs),
            args_schema=ProcessPDFFromURLSchema
        ),
        StructuredTool(
            name="mistral_ocr_process_local_file",
            description="Process a local PDF or image file using Mistral OCR",
            func=lambda **kwargs: integration.process_local_file(**kwargs),
            args_schema=ProcessLocalFileSchema
        ),
        StructuredTool(
            name="mistral_ocr_document_understanding",
            description="Process a document and get answers to questions about its content",
            func=lambda **kwargs: integration.document_understanding(**kwargs),
            args_schema=DocumentUnderstandingSchema
        ),
        StructuredTool(
            name="mistral_ocr_batch_process_files",
            description="Process multiple files in a directory using Mistral OCR",
            func=lambda **kwargs: integration.batch_process_files(**kwargs),
            args_schema=BatchProcessFilesSchema
        ),
    ] 
#!/usr/bin/env python3
"""
Test script for DocumentOCR

This script tests the DocumentOCRWorkflow to process documents.
"""

import os
import sys
from pathlib import Path
from src import secret
from src.custom.DocumentOCR.integrations.MistralOCRIntegration import (
    MistralOCRIntegration,
    MistralOCRIntegrationConfiguration
)
from src.custom.DocumentOCR.workflows.DocumentOCRWorkflow import (
    DocumentOCRWorkflow,
    DocumentOCRWorkflowConfiguration,
    ProcessDocumentParameters
)

def test_process_document(file_path):
    """Test processing a document with OCR using the DocumentOCR integration.
    
    Args:
        file_path (str): Path to the document to process
    
    Returns:
        dict: Processing results
    """
    # Configure the integration
    integration_config = MistralOCRIntegrationConfiguration(
        api_key=os.environ.get("MISTRAL_API_KEY") or secret.get("MISTRAL_API_KEY"),
        storage_path="storage/datastore"
    )
    
    # Create workflow configuration
    workflow_config = DocumentOCRWorkflowConfiguration(
        integration_config=integration_config,
        storage_path="storage/datastore"
    )
    
    # Initialize the workflow
    workflow = DocumentOCRWorkflow(workflow_config)
    
    # Define the output path
    input_path = Path(file_path)
    output_path = str(input_path.parent / f"{input_path.stem}_ocr_test.txt")
    
    print(f"Processing document: {file_path}")
    print(f"Output path: {output_path}")
    
    # Process the document
    result = workflow.process_document(
        ProcessDocumentParameters(
            file_path=file_path,
            output_path=output_path,
            include_image_base64=False
        )
    )
    
    # Check if the processing was successful
    if result and result.get("status") == "success":
        print("✅ Document processing successful!")
        print(f"OCR results saved to: {output_path}")
        
        # Print a snippet of the extracted text
        if "text_content" in result:
            text_snippet = result["text_content"][:500] + "..." if len(result["text_content"]) > 500 else result["text_content"]
            print("\nExtracted text snippet:")
            print("-" * 80)
            print(text_snippet)
            print("-" * 80)
    else:
        print("❌ Document processing failed!")
        print(result)
    
    return result

if __name__ == "__main__":
    # Get file path from command line
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Default test file
        file_path = "storage/datastore/sample_documents/test_document.pdf"
    
    # Run the test
    test_process_document(file_path) 
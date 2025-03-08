# Document OCR and Understanding Module

This module provides document processing capabilities using Mistral OCR and document understanding technology. It allows you to extract text from documents, maintain document structure, and interact with document content using natural language.

## Features

- **OCR Processing**: Extract text from PDF documents and images while preserving formatting
- **Document Understanding**: Ask questions about document content using natural language
- **Batch Processing**: Process multiple documents at once
- **Integration with Storage**: Works with files in your storage directories
- **Structured Output**: Returns results in a structured format for easy parsing

## Module Structure

The module is organized into the following components:

```
src/custom/DocumentOCR/
├── __init__.py           # Main module exports
├── README.md             # This file
├── demo.py               # Interactive demo script
├── assistants/           # Agent implementation
│   ├── __init__.py
│   └── DocumentOCRAgent.py
├── integrations/         # Core integration with Mistral OCR API
│   ├── __init__.py
│   └── MistralOCRIntegration.py
├── models/               # ML models (placeholder for future use)
│   └── __init__.py
├── pipelines/            # Pipeline for document processing
│   ├── __init__.py
│   └── DocumentOCRPipeline.py
└── workflows/            # Workflow for document operations
    ├── __init__.py
    └── DocumentOCRWorkflow.py
```

## Components

The module consists of four main components:

1. **MistralOCRIntegration**: Core integration with Mistral's OCR API
2. **DocumentOCRPipeline**: Pipeline for processing documents and storing results in ontology
3. **DocumentOCRWorkflow**: Workflow for document processing operations
4. **DocumentOCRAgent**: Agent that provides a natural language interface to the document processing capabilities

## Setup

### API Keys

This module requires the following API keys to be set:

1. **Mistral API Key**: Used for OCR and document understanding
   - Add to your `.env` file: `MISTRAL_API_KEY=your_mistral_key_here`
   - Sign up at [Mistral AI](https://mistral.ai/) to get your API key

2. **OpenAI API Key** (for the agent): Used for natural language processing
   - Add to your `.env` file: `OPENAI_API_KEY=your_openai_key_here`

## Usage

### Using the Chat Agent

The easiest way to use this module is through the chat agent interface:

```bash
make chat-documentocr-agent
```

This will start an interactive terminal where you can:
- Provide document paths to process (relative to the storage directory)
- Ask questions about document content
- Process batches of documents

The agent will handle the OCR processing and save results in the same directory as the input files.

### Basic Usage (Code)

```python
from src.custom.DocumentOCR import create_agent

# Create the Document OCR Agent
agent = create_agent(
    mistral_api_key="your-mistral-api-key",
    openai_api_key="your-openai-api-key"
)

# Process a document with OCR
response = agent.run("Extract text from the document at /storage/datastore/reports/financial_report.pdf")

# Get answers about document content
response = agent.run("Read /storage/datastore/contracts/agreement.pdf and tell me when it expires")

# Batch process documents
response = agent.run("Process all PDF documents in the /storage/datastore/invoices directory")
```

### Advanced Usage

For more advanced usage, you can directly use the integration, pipeline, or workflow components:

```python
from src.custom.DocumentOCR import (
    MistralOCRIntegration, 
    MistralOCRIntegrationConfiguration,
    DocumentOCRWorkflow, 
    DocumentOCRWorkflowConfiguration, 
    ProcessDocumentParameters
)

# Configure the integration
integration_config = MistralOCRIntegrationConfiguration(
    api_key="your-mistral-api-key",
    storage_path="/storage/datastore"
)

# Create integration instance
integration = MistralOCRIntegration(integration_config)

# Process a document directly
result = integration.process_local_file(
    file_path="/storage/datastore/reports/financial_report.pdf",
    output_path="/storage/datastore/processed/financial_report_ocr.txt"
)

# Use the workflow for more sophisticated processing
workflow_config = DocumentOCRWorkflowConfiguration(
    integration_config=integration_config,
    storage_path="/storage/datastore"
)

workflow = DocumentOCRWorkflow(workflow_config)

# Process a document through the workflow
result = workflow.process_document(
    ProcessDocumentParameters(
        file_path="reports/financial_report.pdf",
        output_path="processed/financial_report_ocr.txt"
    )
)
```

## Running the Demo

To try out the module, run the included demo script:

```bash
python -m src.custom.DocumentOCR.demo
```

## Requirements

- Python 3.8+
- Mistral AI API key
- OpenAI API key (for the agent)

## File Types Supported

- PDF documents
- Images (JPG, PNG, GIF, BMP, TIFF)

## Configuration

You can configure the module through environment variables:

- `MISTRAL_API_KEY`: Your Mistral API key
- `OPENAI_API_KEY`: Your OpenAI API key (for the agent)

Or by providing the keys directly when creating the components. 